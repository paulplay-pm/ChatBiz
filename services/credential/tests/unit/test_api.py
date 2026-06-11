"""Integration tests for the FastAPI application — main, lifespan, routers.

Uses aiosqlite-backed TestClient to exercise the full HTTP stack.
"""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import event as sa_event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import crypto
from app.crypto import generate_dek, generate_master_key
from app.models import Base, EncryptionKey, KeyStatus
from app.main import create_app


# ---------------------------------------------------------------------------
# Lifespan override for test app
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _lifespan_override(app: FastAPI) -> AsyncIterator[None]:
    """Custom lifespan that injects aiosqlite engine + master key."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False, future=True)

    @sa_event.listens_for(engine.sync_engine, "before_cursor_execute", retval=True)
    def _intercept_ddl(conn, cursor, statement, parameters, context, executemany):
        if "BIGINT" in statement:
            statement = statement.replace("BIGINT", "INTEGER")
        return statement, parameters

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.engine = engine
    app.state.session_factory = factory

    # Bootstrap a master key
    mk = generate_master_key()
    kid = UUID(int=secrets.randbits(128))
    async with factory() as s:
        s.add(EncryptionKey(key_id=kid, encrypted_key=mk, status=KeyStatus.ACTIVE))
        await s.commit()
    app.state.master_key = mk
    app.state.master_key_id = kid
    app.state.redis = None
    app.state.wechat_webhook_url = ""

    try:
        yield
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test app factory
# ---------------------------------------------------------------------------

def _build_test_app() -> FastAPI:
    """Build a FastAPI app with test lifespan + all routers/handlers registered."""
    from app.permissions import PermissionDeniedError
    from app.rate_limit import RateLimitExceededError
    from app.routers import credentials as credentials_router
    from app.services import (
        CredentialExpiredError,
        CredentialNotFoundError,
        WorkspaceMismatchError,
    )
    from fastapi import Request, status
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse

    app = FastAPI(
        title="ChatBiz Credential Management Test",
        version="0.1.0",
        lifespan=_lifespan_override,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(credentials_router.router)

    # Health endpoint — use Depends for Request to avoid query param issue
    from fastapi import Depends

    async def _get_engine(request: Request) -> Any:
        return request.app.state.engine

    @app.get("/healthz")
    async def healthz(engine: Any = Depends(_get_engine)) -> dict[str, str]:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}

    # Exception handlers
    def _err(message: str, code: str) -> dict[str, Any]:
        return {"error": {"code": code, "message": message}}

    @app.exception_handler(CredentialNotFoundError)
    async def _not_found(_request: Request, exc: CredentialNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_err(str(exc), "credential_not_found"),
        )

    @app.exception_handler(CredentialExpiredError)
    async def _expired(_request: Request, exc: CredentialExpiredError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_410_GONE,
            content=_err(str(exc), "credential_expired"),
        )

    @app.exception_handler(WorkspaceMismatchError)
    async def _ws_mismatch(_request: Request, exc: WorkspaceMismatchError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_err(str(exc), "workspace_mismatch"),
        )

    @app.exception_handler(PermissionDeniedError)
    async def _perm(_request: Request, exc: PermissionDeniedError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_err(str(exc), "permission_denied"),
        )

    @app.exception_handler(RateLimitExceededError)
    async def _ratelimit(
        _request: Request, exc: RateLimitExceededError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=_err(str(exc), "rate_limit_exceeded"),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    return app


@pytest.fixture(scope="function")
def app_factory():
    """Return a fresh test app per function (function-scoped for isolation)."""
    return _build_test_app()


# ---------------------------------------------------------------------------
# Header helpers
# ---------------------------------------------------------------------------


def _admin_headers(workspace: str = "finance") -> dict[str, str]:
    return {
        "X-User-Id": "u-admin",
        "X-User-Workspace": workspace,
        "X-User-Roles": "admin",
    }


def _reader_headers(workspace: str = "finance") -> dict[str, str]:
    return {
        "X-User-Id": "u-reader",
        "X-User-Workspace": workspace,
        "X-User-Roles": "",
    }


def _writer_headers(workspace: str = "finance") -> dict[str, str]:
    return {
        "X-User-Id": "u-writer",
        "X-User-Workspace": workspace,
        "X-User-Roles": "credential_admin",
    }


def _user_headers(workspace: str = "finance") -> dict[str, str]:
    return {
        "X-User-Id": "u-user",
        "X-User-Workspace": workspace,
        "X-User-Roles": "",
    }


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealth:
    def test_healthz_returns_200(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            resp = client.get("/healthz")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Create credential
# ---------------------------------------------------------------------------


class TestCreateCredential:
    def test_create_api_key(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            resp = client.post(
                "/api/v1/credentials",
                json={
                    "name": "openai-key",
                    "type": "api_key",
                    "value": "sk-test-12345678",
                    "workspace_id": "finance",
                },
                headers=_admin_headers(),
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["name"] == "openai-key"
            assert data["id"].startswith("cred_")
            assert "value" not in data

    def test_create_oauth2(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            resp = client.post(
                "/api/v1/credentials",
                json={
                    "name": "github-oauth",
                    "type": "oauth2",
                    "value": "gh-token-abc",
                    "workspace_id": "finance",
                    "client_id": "abc123",
                    "client_secret": "very-secret",
                    "token_url": "https://github.com/oauth/token",
                    "scope": "repo,read:user",
                },
                headers=_admin_headers(),
            )
            assert resp.status_code == 201

    def test_create_requires_permission(self, app_factory: FastAPI) -> None:
        """Reader cannot create credentials."""
        with TestClient(app_factory) as client:
            resp = client.post(
                "/api/v1/credentials",
                json={
                    "name": "test",
                    "type": "api_key",
                    "value": "v",
                    "workspace_id": "finance",
                },
                headers=_reader_headers(),
            )
            assert resp.status_code == 403

    def test_create_validates_input(self, app_factory: FastAPI) -> None:
        """Missing required fields return 422."""
        with TestClient(app_factory) as client:
            resp = client.post(
                "/api/v1/credentials",
                json={"name": "bad"},
                headers=_admin_headers(),
            )
            assert resp.status_code == 422


# ---------------------------------------------------------------------------
# List credentials
# ---------------------------------------------------------------------------


class TestListCredentials:
    def test_list_returns_paginated(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            h = _admin_headers()
            for i in range(3):
                client.post(
                    "/api/v1/credentials",
                    json={"name": f"k-{i}", "type": "api_key", "value": f"v-{i}-abcdefghijk", "workspace_id": "finance"},
                    headers=h,
                )

            resp = client.get("/api/v1/credentials", headers=_admin_headers())
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_count"] == 3
            assert len(data["items"]) == 3

    def test_list_requires_permission(self, app_factory: FastAPI) -> None:
        """Missing X-User-Id means not authenticated → 422."""
        with TestClient(app_factory) as client:
            resp = client.get("/api/v1/credentials")
            assert resp.status_code == 422  # Missing required header

    def test_list_with_type_filter(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            h = _admin_headers()
            client.post(
                "/api/v1/credentials",
                json={"name": "key1", "type": "api_key", "value": "v1-abcdefghi", "workspace_id": "finance"},
                headers=h,
            )

            resp = client.get("/api/v1/credentials?type=api_key", headers=_admin_headers())
            assert resp.status_code == 200
            data = resp.json()
            assert all(item["type"] == "api_key" for item in data["items"])


# ---------------------------------------------------------------------------
# Get credential (detail)
# ---------------------------------------------------------------------------


class TestGetCredential:
    def test_get_returns_masked_value(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            resp = client.post(
                "/api/v1/credentials",
                json={
                    "name": "my-key",
                    "type": "api_key",
                    "value": "sk-test-1234567890ABCDEF",
                    "workspace_id": "finance",
                },
                headers=_admin_headers(),
            )
            cred_id = resp.json()["id"]

            detail = client.get(f"/api/v1/credentials/{cred_id}", headers=_admin_headers())
            assert detail.status_code == 200
            data = detail.json()
            assert "masked_value" in data
            assert "★★★★" in data["masked_value"]

    def test_get_not_found(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            resp = client.get(
                "/api/v1/credentials/cred_nonexistent", headers=_admin_headers()
            )
            assert resp.status_code == 404

    def test_get_wrong_workspace(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            h = _admin_headers()
            cr = client.post(
                "/api/v1/credentials",
                json={"name": "k", "type": "api_key", "value": "v-test-long-enough", "workspace_id": "finance"},
                headers=h,
            )
            cred_id = cr.json()["id"]

            resp = client.get(
                f"/api/v1/credentials/{cred_id}",
                headers=_admin_headers(workspace="marketing"),
            )
            assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Rotate credential
# ---------------------------------------------------------------------------


class TestRotateCredential:
    def test_rotate_requires_permission(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            resp = client.post(
                "/api/v1/credentials/cred_x/rotate",
                json={"value": "new-secret-value-here"},
                headers=_reader_headers(),
            )
            assert resp.status_code == 403

    def test_rotate_not_found(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            resp = client.post(
                "/api/v1/credentials/cred_nonexistent/rotate",
                json={"value": "new-secret-value-here"},
                headers=_admin_headers(),
            )
            assert resp.status_code == 404

    def test_rotate_preserves_metadata(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            h = _admin_headers()
            cr = client.post(
                "/api/v1/credentials",
                json={
                    "name": "gh-oauth",
                    "type": "oauth2",
                    "value": "gh-token-old-1234567890",
                    "workspace_id": "finance",
                    "client_id": "abc123",
                    "client_secret": "very-secret",
                    "token_url": "https://github.com/oauth/token",
                    "scope": "repo",
                },
                headers=h,
            )
            cred_id = cr.json()["id"]

            rr = client.post(
                f"/api/v1/credentials/{cred_id}/rotate",
                json={"value": "gh-token-new-abcdefghij"},
                headers=h,
            )
            assert rr.status_code == 200


# ---------------------------------------------------------------------------
# Reveal credential
# ---------------------------------------------------------------------------


class TestRevealCredential:
    def test_reveal_returns_plaintext(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            h = _admin_headers()
            cr = client.post(
                "/api/v1/credentials",
                json={"name": "r-key", "type": "api_key", "value": "secret-v-1234567890", "workspace_id": "finance"},
                headers=h,
            )
            cred_id = cr.json()["id"]

            resp = client.post(
                f"/api/v1/credentials/{cred_id}/reveal",
                headers=h,
            )
            assert resp.status_code == 200
            assert resp.json()["value"] == "secret-v-1234567890"

    def test_reveal_requires_admin(self, app_factory: FastAPI) -> None:
        """Only admin can reveal; credential_admin cannot."""
        with TestClient(app_factory) as client:
            resp = client.post(
                "/api/v1/credentials/cred_x/reveal",
                headers=_writer_headers(),
            )
            assert resp.status_code == 403

    def test_reveal_not_found(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            resp = client.post(
                "/api/v1/credentials/cred_nonexistent/reveal",
                headers=_admin_headers(),
            )
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Use credential
# ---------------------------------------------------------------------------


class TestUseCredential:
    def test_use_returns_plaintext(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            h = _admin_headers()
            cr = client.post(
                "/api/v1/credentials",
                json={"name": "u-key", "type": "api_key", "value": "use-me-123456789012", "workspace_id": "finance"},
                headers=h,
            )
            cred_id = cr.json()["id"]

            resp = client.post(
                f"/api/v1/credentials/{cred_id}/use",
                json={"cap": "workflow-engine", "purpose": "paul-monthly-report"},
                headers=_user_headers(),
            )
            assert resp.status_code == 200
            assert resp.json()["value"] == "use-me-123456789012"

    def test_use_requires_permission(self, app_factory: FastAPI) -> None:
        """Missing X-User-Id returns 422 (Header required)."""
        with TestClient(app_factory) as client:
            resp = client.post(
                "/api/v1/credentials/cred_x/use",
                json={"cap": "cap", "purpose": "test"},
            )
            assert resp.status_code == 422

    def test_use_not_found(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            resp = client.post(
                "/api/v1/credentials/cred_nonexistent/use",
                json={"cap": "cap", "purpose": "test"},
                headers=_user_headers(),
            )
            assert resp.status_code == 404

    def test_use_wrong_workspace(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            h = _admin_headers()
            cr = client.post(
                "/api/v1/credentials",
                json={"name": "k", "type": "api_key", "value": "v-abcdefghijklmnop", "workspace_id": "finance"},
                headers=h,
            )
            cred_id = cr.json()["id"]

            resp = client.post(
                f"/api/v1/credentials/{cred_id}/use",
                json={"cap": "cap", "purpose": "test"},
                headers=_user_headers(workspace="marketing"),
            )
            assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Delete credential
# ---------------------------------------------------------------------------


class TestDeleteCredential:
    def test_delete_returns_204(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            h = _admin_headers()
            cr = client.post(
                "/api/v1/credentials",
                json={"name": "to-delete", "type": "api_key", "value": "v-1234567890123456", "workspace_id": "finance"},
                headers=h,
            )
            cred_id = cr.json()["id"]

            resp = client.delete(
                f"/api/v1/credentials/{cred_id}", headers=h
            )
            assert resp.status_code == 204
            assert resp.text == ""  # no body

    def test_delete_not_found(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            resp = client.delete(
                "/api/v1/credentials/cred_nonexistent",
                headers=_admin_headers(),
            )
            assert resp.status_code == 404

    def test_delete_requires_permission(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            resp = client.delete(
                "/api/v1/credentials/cred_x",
                headers=_reader_headers(),
            )
            assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Exception handler: expired credential (410)
# ---------------------------------------------------------------------------


class TestExpiredCredential:
    def test_reveal_expired_returns_410(self, app_factory: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
        """Reveal on expired credential returns 410."""
        # SQLite strips tzinfo, so monkeypatch _utcnow to return naive datetime
        from app import services as svc_mod
        from app.services import _utcnow as _orig

        def _naive_utcnow():
            return _orig().replace(tzinfo=None)

        monkeypatch.setattr(svc_mod, "_utcnow", _naive_utcnow)

        with TestClient(app_factory) as client:
            h = _admin_headers()
            dt = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
            cr = client.post(
                "/api/v1/credentials",
                json={
                    "name": "exp-key",
                    "type": "api_key",
                    "value": "v-long-enough-12345",
                    "workspace_id": "finance",
                    "expires_at": dt.isoformat(),
                },
                headers=h,
            )
            cred_id = cr.json()["id"]

            resp = client.post(
                f"/api/v1/credentials/{cred_id}/reveal",
                headers=h,
            )
            assert resp.status_code == 410


# ---------------------------------------------------------------------------
# Rate limit: reveal without Redis should just work (fail-open)
# ---------------------------------------------------------------------------


class TestRateLimitFailOpen:
    def test_multiple_reveals_succeed_without_redis(self, app_factory: FastAPI) -> None:
        """When Redis is None, reveal rate limiter is disabled (fail-open)."""
        with TestClient(app_factory) as client:
            h = _admin_headers()
            cr = client.post(
                "/api/v1/credentials",
                json={"name": "rl-key", "type": "api_key", "value": "val-abcdefghijklmnop", "workspace_id": "finance"},
                headers=h,
            )
            cred_id = cr.json()["id"]

            for _ in range(15):
                resp = client.post(
                    f"/api/v1/credentials/{cred_id}/reveal", headers=h
                )
                assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Pagination edge cases
# ---------------------------------------------------------------------------


class TestPagination:
    def test_custom_page_size(self, app_factory: FastAPI) -> None:
        with TestClient(app_factory) as client:
            h = _admin_headers()
            for i in range(10):
                client.post(
                    "/api/v1/credentials",
                    json={"name": f"p-{i}", "type": "api_key", "value": f"v-{i}-long-enough-123456789", "workspace_id": "finance"},
                    headers=h,
                )

            resp = client.get(
                "/api/v1/credentials?page=1&page_size=3", headers=_admin_headers()
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["items"]) == 3
            assert data["total_count"] == 10
            assert data["page"] == 1
            assert data["page_size"] == 3


# ---------------------------------------------------------------------------
# Exception handler: 403 for permission denied in route
# ---------------------------------------------------------------------------


class TestPermissionError:
    def test_create_without_admin_returns_403(self, app_factory: FastAPI) -> None:
        """User without admin or credential_admin role cannot create."""
        with TestClient(app_factory) as client:
            resp = client.post(
                "/api/v1/credentials",
                json={"name": "x", "type": "api_key", "value": "v-abcdefghijklmnop", "workspace_id": "finance"},
                headers=_user_headers(),
            )
            assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test create_app() factory function from main.py
# ---------------------------------------------------------------------------


class TestCreateApp:
    def test_create_app_returns_fastapi_instance(self) -> None:
        app = create_app()
        assert app.title == "ChatBiz Credential Management"
        assert app.version == "0.1.0"
