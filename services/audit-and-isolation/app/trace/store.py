"""Trace id → event list store with two-tier lookup.

Locks decision D6 in
``openspec/changes/gateway-egress-enforcement-p0/design.md``:

* **Tier 1 (Redis, hot).** Key prefix ``trace:cache:{trace_id}`` in
  Redis db 0, TTL 5 minutes. The cached value is a JSON array of
  audit events for the trace. P99 hit < 100ms.
* **Tier 2 (PostgreSQL, cold).** ``audit_log`` table — the source
  of truth. P99 hit < 500ms.

The split exists so the cross-instance query endpoint can serve
99% of requests from Redis (which both instances share) while the
PG fallback is reserved for traces older than 5 minutes (the warm
cache is the canonical fast path).

When PG returns a hit, the result is *re-cached* in Redis with a
5-minute TTL — so a single hot trace that misses the cache once
becomes a Tier-1 hit for the next 5 minutes on every instance.

Redis errors never propagate: the store always falls through to PG
and returns whatever PG says. A Redis-side exception is logged
once and treated as a cache miss; the caller's latency budget is
preserved at the PG P99.

Schema of the cached event (one element of the list):

    {
      "id": <int>,                # audit_log.id
      "trace_id": <str>,
      "user_id": <str>,
      "workflow_id": <str|None>,
      "model": <str>,
      "model_kind": <str>,
      "bypass_isolation": <bool>,
      "pii_detected_types": [<str>...],
      "pii_redacted_count": <int>,
      "prompt_hash": <str>,
      "token_input": <int|None>,
      "token_output": <int|None>,
      "latency_ms": <int>,
      "upstream_status": <int|None>,
      "error_class": <str|None>,
      "created_at": <iso8601 str>
    }
"""
from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)

# D6 / spec: cache TTL is 5 minutes (300s) and the namespace prefix is
# ``trace:cache:``. The prefix MUST match the cross-instance query
# spec — see ``openspec/changes/gateway-egress-enforcement-p0/specs/
# gateway-trace-cross-instance-query/spec.md`` Requirement 2.
DEFAULT_TTL_SECONDS = 300
CACHE_PREFIX = "trace:cache:"
SOURCE_HIT_REDIS = "redis"
SOURCE_HIT_PG = "pg"


def _cache_key(trace_id: str) -> str:
    """Build the Redis key for ``trace_id``. Pure function for testability."""
    return f"{CACHE_PREFIX}{trace_id}"


def _row_to_event(row: AuditLog) -> dict[str, Any]:
    """Serialise a single ``AuditLog`` row into the cache event shape."""
    return {
        "id": row.id,
        "trace_id": row.trace_id,
        "user_id": row.user_id,
        "workflow_id": row.workflow_id,
        "model": row.model,
        "model_kind": row.model_kind,
        "bypass_isolation": bool(row.bypass_isolation),
        "pii_detected_types": list(row.pii_detected_types or []),
        "pii_redacted_count": row.pii_redacted_count,
        "prompt_hash": row.prompt_hash,
        "token_input": row.token_input,
        "token_output": row.token_output,
        "latency_ms": row.latency_ms,
        "upstream_status": row.upstream_status,
        "error_class": row.error_class,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


class TraceStore:
    """Two-tier trace store: Redis cache → PG fallback.

    The store is constructed once per process and reused. ``redis_client``
    and ``session_factory`` are injected so tests can substitute
    fakeredis and a real (testcontainers) PG without monkey-patching
    module globals.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        session_factory: async_sessionmaker[AsyncSession],
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._redis = redis_client
        self._session_factory = session_factory
        self._ttl = ttl_seconds

    @property
    def cache_prefix(self) -> str:
        """Namespace prefix used for cache keys (exposed for tests)."""
        return CACHE_PREFIX

    @property
    def ttl_seconds(self) -> int:
        """TTL applied to cache writes (exposed for tests)."""
        return self._ttl

    async def _get_from_redis(self, trace_id: str) -> list[dict] | None:
        """Read the cache key, returning ``None`` on miss or Redis error.

        Any Redis exception (connection refused, timeout, type error) is
        caught and logged: callers must see a ``None`` (treated as a
        miss) rather than a 500, because the spec mandates Redis
        failures degrade to PG transparently.
        """
        key = _cache_key(trace_id)
        try:
            raw = await self._redis.get(key)
        except Exception as e:  # noqa: BLE001 — Redis errors are non-fatal
            logger.warning(f"trace cache get failed (treating as miss): {e}")
            return None
        if raw is None:
            return None
        try:
            data = json.loads(raw)
        except (TypeError, ValueError) as e:
            logger.warning(f"trace cache decode failed for {key}: {e}")
            return None
        if not isinstance(data, list):
            return None
        return data

    async def _put_in_redis(self, trace_id: str, events: list[dict]) -> None:
        """Write the event list to the cache. Errors are logged, not raised.

        A failed cache write should not break a successful PG lookup —
        the next request for the same trace will simply re-hit PG.
        """
        key = _cache_key(trace_id)
        try:
            await self._redis.set(key, json.dumps(events), ex=self._ttl)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"trace cache put failed for {key}: {e}")

    async def _get_from_pg(self, trace_id: str) -> list[dict]:
        """Read all rows for ``trace_id`` from ``audit_log``, ascending by time.

        Returns an empty list (not ``None``) when the trace is unknown;
        the endpoint distinguishes "found" from "not found" by list
        length. Sort order is ``id ASC`` which is monotonic in
        ``created_at`` because ``id`` is ``BIGSERIAL`` and
        ``created_at`` defaults to ``now()`` at insert time.
        """
        async with self._session_factory() as session:
            stmt = (
                select(AuditLog)
                .where(AuditLog.trace_id == trace_id)
                .order_by(AuditLog.id.asc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [_row_to_event(r) for r in rows]

    async def get(self, trace_id: str) -> tuple[list[dict], str]:
        """Look up ``trace_id`` and return ``(events, source)``.

        ``source`` is one of ``"redis"`` (Tier 1 hit), ``"pg"`` (Tier 2
        hit, re-cached) or ``"pg"`` with empty list (not found — caller
        decides whether to 404). The list is always sorted by
        ``created_at`` ascending.
        """
        cached = await self._get_from_redis(trace_id)
        if cached is not None:
            return cached, SOURCE_HIT_REDIS
        events = await self._get_from_pg(trace_id)
        if events:
            # Fire-and-forget re-cache. We ``await`` it because the only
            # reason the request would be slow is the extra Redis SET,
            # which is sub-millisecond; not awaiting would force the
            # next caller (within the 5min window) to re-hit PG and
            # waste the same latency budget.
            await self._put_in_redis(trace_id, events)
        return events, SOURCE_HIT_PG


__all__ = [
    "CACHE_PREFIX",
    "DEFAULT_TTL_SECONDS",
    "SOURCE_HIT_PG",
    "SOURCE_HIT_REDIS",
    "TraceStore",
]
