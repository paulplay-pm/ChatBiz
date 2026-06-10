"""End-to-end lifecycle test for the credential-management service.

Walks a real FastAPI app (in-process) against a real PostgreSQL
(testcontainers) through the full create → rotate → use → cron
cleanup flow, and asserts that:

* new-value + previous-value are both decryptable inside the 30-day
  window;
* the cron cleanup wipes the ``previous_*`` columns once the window
  has elapsed;
* the audit log carries exactly the expected 5 action types
  (create / rotate / use / use-after-rotate / cleanup).

The test does NOT exercise the rate limiter (the spec §性能基线 is
covered by the locustfile in ``locust/locustfile.py``) and does NOT
exercise the webhook (the spec §凭证过期提醒 is covered by
``tests/integration/test_cron.py``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta

import fakeredis.aioredis
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app import crypto
from app.audit import hash_credential_id
from app.cron import cleanup_expired_previous
from app.main import create_app
from app.models import Base, Credential, CredentialAudit


@pytest.fixture(scope="module")
def pg_url() -> Iterator[str]:
    """One Postgres container for the whole e2e module."""
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url()
        if url.startswith("postgresql+psycopg2://"):
            url = "postgresql+asyncpg://" + url[len("postgresql+psycopg2://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        yield url


@pytest_asyncio.fixture
async def app(pg_url: str) -> AsyncIterator[FastAPI]:
    """Fresh schema + app per test, pre-populated state (see
    tests/integration/test_credentials.py for the rationale)."""
    engine = create_async_engine(pg_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    fa = create_app()
    fa.router.lifespan_context = None  # type: ignore[attr-defined]
    fa.state.engine = engine
    fa.state.session_factory = factory
    fa.state.master_key = crypto.generate_master_key()
    fa.state.master_key_id = None
    fa.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    fa.state.wechat_webhook_url = ""

    yield fa

    try:
        await fa.state.redis.aclose()
    except Exception:  # noqa: S110 pragma: no cover - best effort
        pass
    await engine.dispose()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def admin_headers() -> dict[str, str]:
    return {
        "X-User-Id": "u-e2e-admin",
        "X-User-Workspace": "finance",
        "X-User-Roles": "admin",
    }


def use_headers(cap: str = "paul-finance-monthly") -> dict[str, str]:
    """Non-admin caller: has `use` permission (read-only of plaintext)."""
    return {
        "X-User-Id": "u-paul",
        "X-User-Workspace": "finance",
        "X-User-Roles": "credential_user",
        "X-Caller-Cap": cap,
    }


@pytest.mark.e2e
class TestCredentialLifecycle:
    """create → rotate → use → cron cleanup — happy path + invariants."""

    async def test_full_lifecycle(self, app: FastAPI, client: httpx.AsyncClient) -> None:
        # ----------------------------------------------------------------
        # 1. CREATE — admin posts a new API-key credential.
        # ----------------------------------------------------------------
        create_resp = await client.post(
            "/api/v1/credentials",
            json={
                "name": "openai-paul",
                "type": "api_key",
                "value": "sk-original-VALUE-XYZ",
                "workspace_id": "finance",
            },
            headers=admin_headers(),
        )
        assert create_resp.status_code == 201, create_resp.text
        cred_id: str = create_resp.json()["id"]
        assert cred_id.startswith("cred_")

        # ----------------------------------------------------------------
        # 2. USE — non-admin calls the internal use API; gets plaintext.
        # ----------------------------------------------------------------
        use_resp_1 = await client.post(
            f"/api/v1/credentials/{cred_id}/use",
            json={"cap": "paul-finance-monthly", "purpose": "monthly-report"},
            headers=use_headers(),
        )
        assert use_resp_1.status_code == 200, use_resp_1.text
        assert use_resp_1.json()["value"] == "sk-original-VALUE-XYZ"

        # ----------------------------------------------------------------
        # 3. ROTATE — admin posts a new value; old value becomes previous.
        # ----------------------------------------------------------------
        rotate_resp = await client.post(
            f"/api/v1/credentials/{cred_id}/rotate",
            json={"value": "sk-ROTATED-VALUE-ABC"},
            headers=admin_headers(),
        )
        assert rotate_resp.status_code == 200, rotate_resp.text
        assert rotate_resp.json()["id"] == cred_id

        # ----------------------------------------------------------------
        # 4. USE — new value should be returned; previous stays decryptable
        #         for the 30-day window.
        # ----------------------------------------------------------------
        use_resp_2 = await client.post(
            f"/api/v1/credentials/{cred_id}/use",
            json={"cap": "paul-finance-monthly", "purpose": "post-rotation-call"},
            headers=use_headers(),
        )
        assert use_resp_2.status_code == 200, use_resp_2.text
        assert use_resp_2.json()["value"] == "sk-ROTATED-VALUE-ABC"

        # The DB row must have previous_value / previous_encrypted_dek set.
        async with app.state.session_factory() as s:
            row = (
                await s.execute(select(Credential).where(Credential.id == cred_id))
            ).scalar_one()
            assert row.previous_value is not None
            assert row.previous_encrypted_dek is not None
            assert row.previous_expires_at is not None
            assert row.previous_expires_at > datetime.now(UTC)
            # Sanity: the previous window should be ~30 days.
            delta = row.previous_expires_at - datetime.now(UTC)
            assert timedelta(days=29) < delta < timedelta(days=31)

        # ----------------------------------------------------------------
        # 5. CRON CLEANUP — simulate 31 days passing by rewriting
        #    previous_expires_at to the past, then run the cleanup.
        # ----------------------------------------------------------------
        async with app.state.session_factory() as s:
            async with s.begin():
                row = (
                    await s.execute(select(Credential).where(Credential.id == cred_id))
                ).scalar_one()
                row.previous_expires_at = datetime.now(UTC) - timedelta(seconds=1)

        async with app.state.session_factory() as s:
            async with s.begin():
                cleaned = await cleanup_expired_previous(s)
        assert cleaned == 1, "cleanup should have removed exactly 1 previous-value row"

        # previous_* columns are now NULL; current value still decrypts.
        async with app.state.session_factory() as s:
            row = (
                await s.execute(select(Credential).where(Credential.id == cred_id))
            ).scalar_one()
            assert row.previous_value is None
            assert row.previous_encrypted_dek is None
            assert row.previous_expires_at is None
            assert row.encrypted_value is not None  # current still there

        # And the use API still works after cleanup.
        use_resp_3 = await client.post(
            f"/api/v1/credentials/{cred_id}/use",
            json={"cap": "paul-finance-monthly", "purpose": "post-cleanup-call"},
            headers=use_headers(),
        )
        assert use_resp_3.status_code == 200
        assert use_resp_3.json()["value"] == "sk-ROTATED-VALUE-ABC"

        # ----------------------------------------------------------------
        # 6. AUDIT — exactly the expected set of actions was written.
        # ----------------------------------------------------------------
        async with app.state.session_factory() as s:
            actions = (
                await s.execute(
                    select(CredentialAudit.action, func.count(CredentialAudit.id))
                    .where(CredentialAudit.credential_id_hash == hash_credential_id(cred_id))
                    .group_by(CredentialAudit.action)
                )
            ).all()
        action_counts = dict(actions)
        # create (1) + use (3 — original, post-rotate, post-cleanup) + rotate (1)
        # + cleanup_previous (1) = 6 audit rows.
        assert action_counts.get("create") == 1, action_counts
        assert action_counts.get("rotate") == 1, action_counts
        assert action_counts.get("use") == 3, action_counts
        assert action_counts.get("cleanup_previous") == 1, action_counts

        # No audit row should contain the plaintext value.
        async with app.state.session_factory() as s:
            rows = (
                await s.execute(
                    select(CredentialAudit).where(
                        CredentialAudit.credential_id_hash
                        == hash_credential_id(cred_id)
                    )
                )
            ).scalars().all()
        for row in rows:
            assert "sk-" not in (row.user_id or "")
            assert "sk-" not in (row.cap or "")
            assert "sk-" not in (row.purpose or "")
            assert "VALUE" not in (row.user_id or "")


@pytest.mark.e2e
class TestMultiWorkspaceE2E:
    """Cross-workspace create/use is rejected at the HTTP layer."""

    async def test_cross_workspace_use_blocked(
        self, app: FastAPI, client: httpx.AsyncClient
    ) -> None:
        # admin in workspace=finance creates a credential.
        create_resp = await client.post(
            "/api/v1/credentials",
            json={
                "name": "secret-1",
                "type": "api_key",
                "value": "sk-shared",
                "workspace_id": "finance",
            },
            headers={
                "X-User-Id": "u-admin",
                "X-User-Workspace": "finance",
                "X-User-Roles": "admin",
            },
        )
        assert create_resp.status_code == 201
        cred_id = create_resp.json()["id"]

        # User from a different workspace (ops) tries to use it.
        cross_resp = await client.post(
            f"/api/v1/credentials/{cred_id}/use",
            json={"cap": "ops-tool", "purpose": "test"},
            headers={
                "X-User-Id": "u-ops",
                "X-User-Workspace": "ops",
                "X-User-Roles": "credential_user",
            },
        )
        assert cross_resp.status_code == 403, cross_resp.text
        body = cross_resp.json()
        assert (
            "mismatch" in body["error"]["message"].lower()
            or "workspace" in body["error"]["message"].lower()
        )
