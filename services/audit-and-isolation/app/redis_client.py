"""Async Redis client for the audit-and-isolation service.

The gateway uses Redis for three orthogonal concerns:

* **Per-trace PII placeholder map** (key ``redact:trace:<trace_id>``,
  TTL ``pii_map_ttl_seconds``). Holds the placeholder→original map so
  the response-side reverser can swap the PII back in. The map never
  reaches the database.
* **Routing table cache** (key ``routing:model:<model_name>``, TTL
  ``routing_table_ttl_seconds``). Hot-updated by the dispatcher's
  startup loader; the in-process dict in ``routing/table.py`` is the
  Redis-down fallback.
* **Future: credential cache + rate limit counters** (not in MVP).

A single module-level connection pool with ``max_connections=50`` is
shared across coroutines. ``decode_responses=True`` means ``GET`` and
``SET`` round-trip as ``str`` (matching the JSON-encoded payloads the
rest of the gateway stores); callers that need raw bytes can wrap with
``redis.Redis(..., decode_responses=False)`` locally.

The factory ``get_redis()`` is **cheap to call** — it returns a thin
``redis.Redis`` bound to the cached pool — so callers should call it
per-request rather than caching the client. The pool is the heavy
resource, not the ``Redis`` instance.
"""

from __future__ import annotations

import redis.asyncio as redis

from app.config import get_settings

_pool: redis.ConnectionPool | None = None


def get_redis() -> redis.Redis:
    """Return an async ``redis.Redis`` bound to the cached connection pool.

    The pool is lazily created on first call and reused for the
    process's lifetime. ``max_connections=50`` is sized for the
    gateway's two-instance HA (so 50 in-flight commands per pod
    before the pool starts blocking callers — a level the local
    bench hits at ~300 RPS per pod, well above the 100 RPS SLO
    target).
    """
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(
            get_settings().redis_url,
            max_connections=50,
            decode_responses=True,
        )
    return redis.Redis(connection_pool=_pool)


def reset_pool_for_tests() -> None:
    """Drop the cached pool. Test-only helper — never call from
    production code (would orphan live connections on the next
    ``get_redis()``)."""
    global _pool
    _pool = None


__all__ = ["get_redis", "reset_pool_for_tests"]
