"""Unit tests for liveness/readiness probes.

The readiness probe touches external boundaries (PostgreSQL, Redis,
credential service). These tests keep the endpoint behavior real while
patching those boundaries with tiny fakes so no real service is needed.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import pytest
from fastapi import Response

import app.redis_client as redis_client
from app.api import health


class _SessionContext:
    def __init__(self, *, error: Exception | None = None):
        self.error = error
        self.executed = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def execute(self, statement):
        self.executed.append(statement)
        if self.error is not None:
            raise self.error
        return None


class _Redis:
    def __init__(self, *, error: Exception | None = None):
        self.error = error
        self.pinged = False

    async def ping(self):
        self.pinged = True
        if self.error is not None:
            raise self.error
        return True


class _AsyncClient:
    error: Exception | None = None
    posts: list[dict] = []

    def __init__(self, *, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def post(self, url, json):
        type(self).posts.append({"url": url, "json": json, "timeout": self.timeout})
        error = type(self).error
        if error is not None:
            raise error
        return SimpleNamespace(status_code=401)


@pytest.fixture(autouse=True, name="reset_async_client")
def _reset_async_client_fixture() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    _AsyncClient.error = None
    _AsyncClient.posts = []
    yield
    _AsyncClient.error = None
    _AsyncClient.posts = []


def _body(response):
    return json.loads(response.body.decode("utf-8"))


@pytest.mark.asyncio
async def test_healthz_returns_ok_status():
    from fastapi import FastAPI

    from starlette.testclient import TestClient

    test_app = FastAPI()
    test_app.state.draining = False
    test_app.include_router(health.router)
    client = TestClient(test_app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readyz_returns_200_when_all_dependencies_are_ready():
    session = _SessionContext()
    redis = _Redis()

    with (
        patch.object(health, "get_session", return_value=session),
        patch.object(redis_client, "get_redis", return_value=redis),
        patch.object(health, "get_settings", return_value=SimpleNamespace(credential_service_url="http://credential")),
        patch.object(health.httpx, "AsyncClient", _AsyncClient),
        patch.object(health, "_inmemory", {"qwen-max": {"model_kind": "public"}}),
    ):
        response = cast(Response, await health.readyz())

    assert response.status_code == 200
    assert _body(response) == {
        "postgres": "ok",
        "redis": "ok",
        "credential_service": "ok",
        "routing_table": "ok",
    }
    assert redis.pinged is True
    assert "SELECT 1" in str(session.executed[0])
    assert _AsyncClient.posts == [
        {
            "url": "http://credential/v1/auth/verify",
            "json": {"token": "", "audience": "audit-and-isolation"},
            "timeout": 2.0,
        }
    ]


@pytest.mark.asyncio
async def test_readyz_returns_503_with_marker_when_postgres_fails():
    with (
        patch.object(health, "get_session", return_value=_SessionContext(error=RuntimeError("pg down"))),
        patch.object(redis_client, "get_redis", return_value=_Redis()),
        patch.object(health, "get_settings", return_value=SimpleNamespace(credential_service_url="http://credential")),
        patch.object(health.httpx, "AsyncClient", _AsyncClient),
        patch.object(health, "_inmemory", {"qwen-max": {}}),
    ):
        response = cast(Response, await health.readyz())

    body = _body(response)
    assert response.status_code == 503
    assert body["postgres"] == "fail: pg down"
    assert body["redis"] == "ok"
    assert body["credential_service"] == "ok"
    assert body["routing_table"] == "ok"


@pytest.mark.asyncio
async def test_readyz_returns_503_with_marker_when_redis_fails():
    with (
        patch.object(health, "get_session", return_value=_SessionContext()),
        patch.object(redis_client, "get_redis", return_value=_Redis(error=RuntimeError("redis down"))),
        patch.object(health, "get_settings", return_value=SimpleNamespace(credential_service_url="http://credential")),
        patch.object(health.httpx, "AsyncClient", _AsyncClient),
        patch.object(health, "_inmemory", {"qwen-max": {}}),
    ):
        response = cast(Response, await health.readyz())

    body = _body(response)
    assert response.status_code == 503
    assert body["postgres"] == "ok"
    assert body["redis"] == "fail: redis down"
    assert body["credential_service"] == "ok"
    assert body["routing_table"] == "ok"


@pytest.mark.asyncio
async def test_readyz_returns_503_with_marker_when_credential_service_fails():
    _AsyncClient.error = RuntimeError("credential down")
    with (
        patch.object(health, "get_session", return_value=_SessionContext()),
        patch.object(redis_client, "get_redis", return_value=_Redis()),
        patch.object(health, "get_settings", return_value=SimpleNamespace(credential_service_url="http://credential")),
        patch.object(health.httpx, "AsyncClient", _AsyncClient),
        patch.object(health, "_inmemory", {"qwen-max": {}}),
    ):
        response = cast(Response, await health.readyz())

    body = _body(response)
    assert response.status_code == 503
    assert body["postgres"] == "ok"
    assert body["redis"] == "ok"
    assert body["credential_service"] == "fail: credential down"
    assert body["routing_table"] == "ok"


@pytest.mark.asyncio
async def test_healthz_returns_503_when_app_state_draining_is_true():
    """Phase B: preStop drain — /healthz returns 503 when app.state.draining."""
    from fastapi import FastAPI

    from app.main import app

    test_app = FastAPI()
    test_app.state.draining = True
    test_app.include_router(health.router)

    from starlette.testclient import TestClient

    with patch.object(health, "logger"):
        client = TestClient(test_app)
        response = client.get("/healthz")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "draining"


@pytest.mark.asyncio
async def test_healthz_returns_200_when_app_state_draining_is_false():
    """Phase B: /healthz returns 200 when not draining."""
    from fastapi import FastAPI

    test_app = FastAPI()
    test_app.state.draining = False
    test_app.include_router(health.router)

    from starlette.testclient import TestClient

    client = TestClient(test_app)
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_healthz_returns_200_when_draining_attribute_missing():
    """Backwards compat: legacy callers that set no draining attr get 200."""
    from fastapi import FastAPI

    test_app = FastAPI()
    test_app.include_router(health.router)

    from starlette.testclient import TestClient

    client = TestClient(test_app)
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readyz_returns_503_with_empty_routing_marker():
    with (
        patch.object(health, "get_session", return_value=_SessionContext()),
        patch.object(redis_client, "get_redis", return_value=_Redis()),
        patch.object(health, "get_settings", return_value=SimpleNamespace(credential_service_url="http://credential")),
        patch.object(health.httpx, "AsyncClient", _AsyncClient),
        patch.object(health, "_inmemory", {}),
    ):
        response = cast(Response, await health.readyz())

    body = _body(response)
    assert response.status_code == 503
    assert body["postgres"] == "ok"
    assert body["redis"] == "ok"
    assert body["credential_service"] == "ok"
    assert body["routing_table"] == "empty"
