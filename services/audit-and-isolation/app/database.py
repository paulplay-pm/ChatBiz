"""Async SQLAlchemy engine + session factory for the audit-and-isolation service.

The engine is built lazily from ``get_settings().database_url`` (which reads
``DATABASE_URL`` from the environment) so tests can override the URL via
``os.environ`` / ``monkeypatch`` before the first call. The session factory
is cached at module level — one ``AsyncEngine`` per process, mirroring the
lifespan-driven pattern used by the credential service.

Use ``get_session()`` as an async context manager:

    async with get_session() as session:
        ...

The context manager commits on a clean exit and rolls back on any
exception. Tests that want the rollback-on-error behaviour for negative
coverage can ignore the commit and just await the body.

Why we keep this here instead of in ``lifespan.py`` (like the credential
service does): the plan in
``openspec/changes/implement-audit-and-isolation/plan.md`` Task 2.4
specifies an ``app.database.get_session()`` context manager that the
seed script (``alembic/seed.py``) and the future audit outbox worker can
both import without going through the FastAPI ``app.state`` indirection.
The seed script in particular must run outside the HTTP server, so a
process-global factory is the simpler choice.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

# Module-level singletons. Lazy-initialised by ``_get_engine()`` /
# ``_get_session_factory()`` so importing this module does not eagerly
# touch the network or require ``DATABASE_URL`` to be set (e.g. when
# collecting the OpenAPI schema).
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _get_engine() -> AsyncEngine:
    """Return the lazily-created ``AsyncEngine`` singleton.

    The engine uses ``pool_pre_ping=True`` so a stale connection left
    over from a previous request does not survive a Postgres restart —
    the same flag the credential service's ``lifespan.py`` uses.
    """
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_settings().database_url,
            pool_pre_ping=True,
        )
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the lazily-created ``async_sessionmaker`` singleton.

    ``expire_on_commit=False`` is required so that accessing attributes
    on an ORM object after the session has been committed does not
    trigger a lazy refresh — a footgun that has bitten this codebase
    before (see the credential service's commit on this flag).
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            _get_engine(),
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a fresh ``AsyncSession``; commit on success, rollback on error.

    Mirrors the FastAPI cookbook pattern for SQLAlchemy 2.x async: one
    session per logical unit of work, wrapped in a ``begin()`` block so
    an unhandled exception rolls back the transaction (including any
    half-written audit row). The session is closed automatically by the
    ``async with factory()`` context manager.
    """
    factory = _get_session_factory()
    async with factory() as session:
        async with session.begin():
            yield session


async def dispose_engine() -> None:
    """Dispose the cached engine. Called from the FastAPI lifespan shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


__all__ = ["dispose_engine", "get_session"]
