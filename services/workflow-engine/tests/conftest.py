"""Shared pytest fixtures for workflow-engine tests.

Hermetic pattern: no real Docker, no real Postgres, no real Redis, no real LLM.

* Database: aiosqlite in-memory (overrides DATABASE_URL via env)
* Redis: fakeredis (monkey-patches app.redis_client.get_redis)
* SessionLocal: re-bound to the in-memory test engine per test
* External HTTP: respx mocks in each individual test
* Auth: just ``X-User-Id: test-user``

Lifespan is **not** started (we use ``ASGITransport`` directly). The
cron jobs in ``app.cron.lifespan`` therefore do not start — the e2e
tests do not depend on them, and the background ``schedule_run``
``asyncio.create_task`` is fine because we don't await it.
"""
from __future__ import annotations

import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base


# ---------------------------------------------------------------------------
# Session-scoped env var setup
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def setup_env():
    """Set env vars BEFORE any app module imports (Settings is read at import).

    Required for ``Settings()`` to construct without raising on missing
    required fields.
    """
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"  # fakeredis catches this
    os.environ["AUDIT_ISOLATION_URL"] = "http://audit-and-isolation-test:8080"
    os.environ["CREDENTIAL_SERVICE_URL"] = "http://credential-test:8000"
    os.environ["KNOWLEDGE_BASE_URL"] = "http://knowledge-base-test:8002"
    os.environ["AGENT_RUNTIME_URL"] = "http://agent-runtime-test:8003"
    os.environ["WORKFLOW_ENGINE_SERVICE_TOKEN"] = "test-token"
    os.environ["WECOM_WEBHOOK_URL"] = ""
    os.environ["DOCKER_SANDBOX_ENABLED"] = "false"  # tests don't have docker
    os.environ["ENVIRONMENT"] = "test"
    yield


# ---------------------------------------------------------------------------
# Per-test in-memory database
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_setup():
    """Create tables in a fresh in-memory SQLite. Each test gets a clean DB.

    Returns the ``AsyncEngine`` so tests can build a session factory bound
    to the same in-memory DB.
    """
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


def make_test_session_factory(engine):
    """Build an ``async_sessionmaker`` bound to the given engine.

    Exposed as a module-level helper so individual test modules can
    import it without depending on a particular fixture name.
    """
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# ---------------------------------------------------------------------------
# Async HTTP client with monkey-patched SessionLocal + Redis
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client(db_setup):
    """httpx ``AsyncClient`` wrapping the FastAPI app.

    Lifespan is **not** started — the test transport does not invoke it.
    This means the cron jobs (``approval_timeout``, ``cleanup``) do not
    run, but background ``asyncio.create_task`` calls from the runner
    still execute. We do not await them; they fail safely inside the
    test event loop.
    """
    import fakeredis.aioredis
    from app.main import app
    import app.database as dbmod
    import app.redis_client as rcm

    # Replace the module-level SessionLocal with one bound to the test engine.
    TestSession = make_test_session_factory(db_setup)
    original_session = dbmod.SessionLocal
    dbmod.SessionLocal = TestSession

    # Replace get_redis() with a fakeredis factory.
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    original_redis_factory = rcm.get_redis
    rcm.get_redis = lambda: fake

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    finally:
        dbmod.SessionLocal = original_session
        rcm.get_redis = original_redis_factory
        await fake.aclose()


# ---------------------------------------------------------------------------
# Auth header factory
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def auth_headers():
    """Default ``X-User-Id`` header dict. Tests can override per-request."""
    return {"X-User-Id": "test-user"}
