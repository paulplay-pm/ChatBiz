"""Async Redis client for the workflow-engine service.

The workflow engine uses Redis for two orthogonal concerns:

* **画布实时状态 (canvas real-time state)** (event-sourced pub/sub
  fan-out — see ``docs/architecture.md`` §4 状态双层). Redis is the
  hot path; PostgreSQL is the source of truth on checkpoint.
* **短期记忆 (short-term conversation memory)** keyed by ``session:<id>``
  (TTL configured per session).

A single module-level ``redis.Redis`` instance with
``max_connections=50`` is shared across coroutines.
``decode_responses=True`` matches the JSON-encoded payloads the rest
of the engine stores.

The factory ``get_redis()`` is **cheap to call** — it returns the
cached ``Redis`` instance — so callers should call it per-request
rather than caching locally.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from app.config import get_settings

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Return the lazily-created shared async ``redis.Redis`` instance."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            get_settings().redis_url,
            decode_responses=True,
            max_connections=50,
        )
    return _redis


async def dispose_redis() -> None:
    """Close the cached Redis client. Call from FastAPI lifespan shutdown."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


__all__ = ["get_redis", "dispose_redis"]
