"""FastAPI lifespan: master-key load, DB engine setup, Redis client setup.

Spec §主密钥加载 mandates that startup either succeeds with the active
master key in process memory or aborts with a non-zero exit code so an
orchestrator (kubernetes, systemd) can restart the pod. We implement
the abort by raising ``SystemExit(1)`` from inside the lifespan: ASGI
servers (uvicorn / hypercorn) propagate the exception and terminate
the process before any request is served.

The lifespan also owns the singletons the rest of the app reads:

* ``app.state.engine``         — async SQLAlchemy ``AsyncEngine``.
* ``app.state.session_factory``— ``async_sessionmaker`` bound to that engine.
* ``app.state.master_key``     — 32 raw bytes (already unwrapped).
* ``app.state.master_key_id``  — UUID for log correlation.
* ``app.state.redis``          — ``redis.asyncio.Redis`` or ``None`` if disabled.

Tests override these by populating ``app.state`` directly before the
``TestClient`` is constructed — see ``tests/integration/test_credentials.py``.

Configuration is read from environment variables once, at startup:

* ``CREDENTIAL_DB_URL``        — asyncpg DSN (required).
* ``CREDENTIAL_REDIS_URL``     — ``redis://...`` URL (optional; when unset
  the rate limiter is disabled with a warning).
* ``CREDENTIAL_WECHAT_WEBHOOK``— webhook URL for expiry alerts (optional).
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import crypto

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup → yield → shutdown for the credential-management service."""
    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------
    db_url = os.environ.get("CREDENTIAL_DB_URL")
    if not db_url:
        logger.critical("CREDENTIAL_DB_URL is not set; cannot start")
        sys.exit(1)

    engine = create_async_engine(db_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.engine = engine
    app.state.session_factory = session_factory

    # Load the active master key. Spec: 主密钥缺失 → exit(1).
    try:
        async with session_factory() as session:
            record = await crypto.load_master_key(session)
    except crypto.MasterKeyNotFoundError:
        logger.critical("no active master key in encryption_keys; aborting startup")
        await engine.dispose()
        sys.exit(1)

    app.state.master_key = record.key
    app.state.master_key_id = record.key_id

    # Redis is optional in MVP (rate limiter degrades to fail-open).
    redis_url = os.environ.get("CREDENTIAL_REDIS_URL")
    if redis_url:
        app.state.redis = aioredis.from_url(redis_url, decode_responses=True)
    else:
        app.state.redis = None
        logger.warning(
            "CREDENTIAL_REDIS_URL not set; reveal rate limiter is disabled"
        )

    app.state.wechat_webhook_url = os.environ.get("CREDENTIAL_WECHAT_WEBHOOK", "")

    logger.info(
        "credential-management service started (master_key_id=%s)",
        record.key_id,
    )

    try:
        yield
    finally:
        # ------------------------------------------------------------------
        # Shutdown
        # ------------------------------------------------------------------
        if app.state.redis is not None:
            try:
                await app.state.redis.aclose()
            except Exception as exc:  # pragma: no cover - best-effort cleanup
                logger.warning("redis close error: %r", exc)
        await engine.dispose()
        logger.info("credential-management service stopped")


__all__ = ["lifespan"]
