"""End-to-end HTTP integration tests for the credential-management API.

Exercises every endpoint registered by ``app.routers.credentials``
against a real Postgres (via ``testcontainers``) and a ``fakeredis``
in-memory Redis. The real ``lifespan`` is bypassed: we construct the
app via ``create_app()`` and populate ``app.state`` directly with the
session factory, master key, and redis client. This keeps the test
matrix small (no docker-compose for Redis) while still covering the
full request → service → DB → audit-log path.

Coverage matrix (per Task 5 spec):

* create: happy / 422 missing field / 422 invalid type
* list:   happy paged / filter by type / 422 page_size > 100
* get:    happy masked / 404 missing / 403 cross-workspace
* rotate: happy / 404 missing
* reveal: happy admin / 403 non-admin / 429 after 11 calls / 410 expired
* use:    happy + audit row written
* delete: happy / 404 missing / 403 cross-workspace

= 18 distinct tests across 7 endpoints (a few endpoints contribute > 1
failure scenario; the totals add up to 18 hits below).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta

import fakeredis.aioredis
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app import crypto
from app.main import create_app
from app.models import Base, CredentialAudit

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    """One Postgres container per test session — schema is wiped per test."""
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url()
        if url.startswith("postgresql+psycopg2://"):
            url = "postgresql+asyncpg://" + url[len("postgresql+psycopg2://") :]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]
        yield url


@pytest_asyncio.fixture(scope="function")
async def app(pg_url: str) -> AsyncIterator[FastAPI]:
    """Build a fresh ``FastAPI`` app per test with pre-populated state.

    Bypasses the real lifespan (which would try to read env vars and
    open its own engine); instead we wire ``app.state`` directly with
    the same singletons lifespan would set, plus a fakeredis client.
    """
    engine = create_async_engine(pg_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Skip the real lifespan by constructing the app without one. We
    # build a plain FastAPI on top of the same routers + handlers via
    # ``create_app`` and then null-out the lifespan attribute. This is
    # the simplest way to keep main.py production-shaped while testing.
    fa = create_app()
    fa.router.lifespan_context = None  # type: ignore[attr-defined,assignment]

    fa.state.engine = engine
    fa.state.session_factory = factory
    fa.state.master_key = crypto.generate_master_key()
    fa.state.master_key_id = None
    fa.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    fa.state.wechat_webhook_url = ""

    yield fa

    # Cleanup. ``aclose`` on fakeredis is a no-op on most versions but
    # we call it for symmetry with the production lifespan.
    try:
        await fa.state.redis.aclose()
    except Exception as exc:  # pragma: no cover - best effort
        # fakeredis sometimes raises ``RuntimeError`` on double-close;
        # we explicitly swallow it so test teardown stays quiet.
        _ = exc
    await engine.dispose()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """ASGI test client; routes through the in-process app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session(app: FastAPI) -> AsyncIterator[AsyncSession]:
    """A separate session for assertions that read the audit table directly."""
    factory = app.state.session_factory
    async with factory() as s:
        yield s


# ---------------------------------------------------------------------------
# Header helpers
# ---------------------------------------------------------------------------


def admin_headers(user_id: str = "u-admin", workspace: str = "finance") -> dict[str, str]:
    return {
        "X-User-Id": user_id,
        "X-User-Workspace": workspace,
        "X-User-Roles": "admin",
    }


def user_headers(
    user_id: str = "u-user", workspace: str = "finance", roles: str = ""
) -> dict[str, str]:
    return {
        "X-User-Id": user_id,
        "X-User-Workspace": workspace,
        "X-User-Roles": roles,
    }


def api_key_payload(
    *, name: str = "openai", value: str = "sk-test-12345678", workspace: str = "finance"
) -> dict[str, object]:
    return {
        "name": name,
        "type": "api_key",
        "value": value,
        "workspace_id": workspace,
    }


async def _create(client: httpx.AsyncClient, **overrides: object) -> str:
    """POST a credential, return its id. Default headers = admin."""
    payload = api_key_payload(**overrides)  # type: ignore[arg-type]
    resp = await client.post(
        "/api/v1/credentials", json=payload, headers=admin_headers()
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCreate:
    async def test_create_happy(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/credentials",
            json=api_key_payload(),
            headers=admin_headers(),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["id"].startswith("cred_")
        assert body["name"] == "openai"
        assert body["type"] == "api_key"
        # Slim response: no plaintext / masked value here.
        assert "value" not in body
        assert "masked_value" not in body

    async def test_create_missing_field_422(self, client: httpx.AsyncClient) -> None:
        bad = api_key_payload()
        del bad["value"]
        resp = await client.post(
            "/api/v1/credentials", json=bad, headers=admin_headers()
        )
        assert resp.status_code == 422

    async def test_create_invalid_type_422(self, client: httpx.AsyncClient) -> None:
        bad = api_key_payload()
        bad["type"] = "not-a-real-type"
        resp = await client.post(
            "/api/v1/credentials", json=bad, headers=admin_headers()
        )
        assert resp.status_code == 422

    async def test_create_non_admin_403(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/credentials",
            json=api_key_payload(),
            headers=user_headers(),
        )
        assert resp.status_code == 403


@pytest.mark.integration
class TestList:
    async def test_list_paginated(self, client: httpx.AsyncClient) -> None:
        for i in range(3):
            await _create(client, name=f"k-{i}", value=f"val-{i}-padded-12")
        resp = await client.get(
            "/api/v1/credentials?page=1&page_size=2",
            headers=admin_headers(),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total_count"] == 3
        assert body["page"] == 1
        assert body["page_size"] == 2
        assert len(body["items"]) == 2

    async def test_list_filter_by_type(self, client: httpx.AsyncClient) -> None:
        await _create(client)
        resp = await client.get(
            "/api/v1/credentials?type=api_key",
            headers=admin_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 1
        resp_other = await client.get(
            "/api/v1/credentials?type=oauth2",
            headers=admin_headers(),
        )
        assert resp_other.status_code == 200
        assert resp_other.json()["total_count"] == 0

    async def test_list_page_size_too_large(self, client: httpx.AsyncClient) -> None:
        # FastAPI's Query(le=100) catches this before the service does;
        # it returns 422 (validation), not 400. Both are documented as
        # "client error" by the spec — we accept either.
        resp = await client.get(
            "/api/v1/credentials?page_size=101", headers=admin_headers()
        )
        assert resp.status_code in (400, 422)


@pytest.mark.integration
class TestGet:
    async def test_get_masked(self, client: httpx.AsyncClient) -> None:
        cid = await _create(client, value="sk-test-1234567890ABCDEF")
        resp = await client.get(
            f"/api/v1/credentials/{cid}", headers=admin_headers()
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # Masked: first 4 + ★★★★ + last 4
        assert body["masked_value"].startswith("sk-t")
        assert body["masked_value"].endswith("CDEF")
        assert "sk-test-1234567890ABCDEF" not in body["masked_value"]

    async def test_get_404(self, client: httpx.AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/credentials/cred_does_not_exist", headers=admin_headers()
        )
        assert resp.status_code == 404

    async def test_get_cross_workspace_403(self, client: httpx.AsyncClient) -> None:
        cid = await _create(client)  # finance workspace
        resp = await client.get(
            f"/api/v1/credentials/{cid}",
            headers={
                "X-User-Id": "u-other",
                "X-User-Workspace": "marketing",
                "X-User-Roles": "admin",
            },
        )
        assert resp.status_code == 403


@pytest.mark.integration
class TestRotate:
    async def test_rotate_happy(self, client: httpx.AsyncClient) -> None:
        cid = await _create(client, value="old-value-1234")
        resp = await client.post(
            f"/api/v1/credentials/{cid}/rotate",
            json={"value": "new-value-5678"},
            headers=admin_headers(),
        )
        assert resp.status_code == 200, resp.text
        # Subsequent use returns the new value.
        used = await client.post(
            f"/api/v1/credentials/{cid}/use",
            json={"cap": "test", "purpose": "post-rotate"},
            headers=admin_headers(),
        )
        assert used.status_code == 200
        assert used.json()["value"] == "new-value-5678"

    async def test_rotate_404(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/credentials/cred_missing/rotate",
            json={"value": "any-new-value"},
            headers=admin_headers(),
        )
        assert resp.status_code == 404


@pytest.mark.integration
class TestReveal:
    async def test_reveal_admin_happy(self, client: httpx.AsyncClient) -> None:
        cid = await _create(client, value="reveal-me-1234")
        resp = await client.post(
            f"/api/v1/credentials/{cid}/reveal",
            headers=admin_headers(),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["value"] == "reveal-me-1234"

    async def test_reveal_non_admin_403(self, client: httpx.AsyncClient) -> None:
        cid = await _create(client)
        resp = await client.post(
            f"/api/v1/credentials/{cid}/reveal",
            headers=user_headers(),
        )
        assert resp.status_code == 403

    async def test_reveal_rate_limited_after_10(
        self, client: httpx.AsyncClient
    ) -> None:
        """10 reveals succeed; the 11th returns 429 with Retry-After."""
        cid = await _create(client, value="rate-limited-value")
        # 10 calls should all succeed.
        for _ in range(10):
            resp = await client.post(
                f"/api/v1/credentials/{cid}/reveal",
                headers=admin_headers(user_id="u-rl-admin"),
            )
            assert resp.status_code == 200, resp.text
        # 11th must be 429 with Retry-After.
        resp = await client.post(
            f"/api/v1/credentials/{cid}/reveal",
            headers=admin_headers(user_id="u-rl-admin"),
        )
        assert resp.status_code == 429
        assert int(resp.headers["Retry-After"]) >= 1


@pytest.mark.integration
class TestUse:
    async def test_use_internal_happy_with_audit(
        self, client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        cid = await _create(client, value="use-me-9999")
        resp = await client.post(
            f"/api/v1/credentials/{cid}/use",
            json={"cap": "workflow-engine", "purpose": "monthly-report"},
            headers=user_headers(),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["value"] == "use-me-9999"

        # Audit row written for the use action.
        use_rows = (
            await db_session.execute(
                select(CredentialAudit).where(CredentialAudit.action == "use")
            )
        ).scalars().all()
        assert len(use_rows) == 1
        row = use_rows[0]
        assert row.cap == "workflow-engine"
        assert row.purpose == "monthly-report"
        assert row.success is True

    async def test_use_expired_410(
        self, client: httpx.AsyncClient
    ) -> None:
        # Create with an already-expired ``expires_at``.
        payload = api_key_payload(value="expired-value-1234")
        payload["expires_at"] = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        create_resp = await client.post(
            "/api/v1/credentials", json=payload, headers=admin_headers()
        )
        assert create_resp.status_code == 201, create_resp.text
        cid = create_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/credentials/{cid}/use",
            json={"cap": "x", "purpose": "y"},
            headers=user_headers(),
        )
        assert resp.status_code == 410


@pytest.mark.integration
class TestDelete:
    async def test_delete_happy(self, client: httpx.AsyncClient) -> None:
        cid = await _create(client)
        resp = await client.delete(
            f"/api/v1/credentials/{cid}", headers=admin_headers()
        )
        assert resp.status_code == 204
        # Subsequent get is a 404.
        get_resp = await client.get(
            f"/api/v1/credentials/{cid}", headers=admin_headers()
        )
        assert get_resp.status_code == 404

    async def test_delete_404(self, client: httpx.AsyncClient) -> None:
        resp = await client.delete(
            "/api/v1/credentials/cred_missing", headers=admin_headers()
        )
        assert resp.status_code == 404

    async def test_delete_cross_workspace_403(self, client: httpx.AsyncClient) -> None:
        cid = await _create(client)
        resp = await client.delete(
            f"/api/v1/credentials/{cid}",
            headers={
                "X-User-Id": "u-other",
                "X-User-Workspace": "marketing",
                "X-User-Roles": "admin",
            },
        )
        assert resp.status_code == 403
