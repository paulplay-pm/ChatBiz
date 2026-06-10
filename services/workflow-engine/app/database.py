"""Async SQLAlchemy engine + session factory for the workflow-engine service.

Engine + session factory are built once at import time from
``get_settings().database_url`` (which reads ``DATABASE_URL`` from the
environment). Tests can override the URL by setting the env var or by
monkeypatching ``get_settings`` before the first call.

Use ``get_session()`` as a FastAPI dependency or directly:

    async for session in get_session():
        ...

The dependency is the standard SQLAlchemy 2.x async pattern: one session
per request, the session is closed by the ``async with`` block in the
factory.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

_settings = get_settings()
engine = create_async_engine(_settings.database_url, pool_pre_ping=True, pool_size=20)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


async def dispose_engine() -> None:
    await engine.dispose()
