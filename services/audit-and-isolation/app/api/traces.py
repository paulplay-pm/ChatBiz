"""GET /v1/traces/{trace_id} — cross-instance trace query endpoint.

Per task 4.1 of `openspec/changes/gateway-egress-enforcement-p0/`. Reads
the audit trail for a single trace_id, with a two-tier lookup:

  L1 (Redis):  ``trace:cache:<trace_id>`` in db 0, 5min TTL. Source of
               truth for the most recent view of an in-flight trace;
               written by the chat endpoint as the outbox enqueues
               each turn. Read latency target: < 100ms.

  L2 (Postgres): ``audit_log`` table WHERE trace_id = ?. Slower (single
               digit ms p50, ~hundreds of ms at p99) but durable.
               Read latency target: < 500ms.

  404:           both tiers miss.

If L1 misses and L2 hits, the L1 cache is **populated** (write-through
on read) so the next call hits L1. This makes the L2 a cold-storage
fallback, not a hot path.

The endpoint is intentionally read-only — it never writes back to the
audit log. Operators use it to debug a single user-visible trace
across the 2-replica K8s deployment (task 2.2): the trace_id is the
join key. ``X-Trace-Id`` from the original request flows into the
audit_log row, so a query for any trace_id will return at least one
row if the chat actually ran.

On Redis failure (the connection is dead, not just a miss), the
endpoint falls through to L2 silently. We don't want a Redis outage
to surface as a 503 — that would mask the audit log fallback.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Path
from sqlalchemy import select

from app import redis_client
from app.database import get_session
from app.models.audit import AuditLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/traces", tags=["traces"])

# L1 cache key prefix. Per spec 4.1: "trace:cache:* namespace,db 0,
# 5min TTL". db 0 is the default for the chatbiz-redis instance
# (see docker-compose*.yml) so we don't pass `db=` explicitly.
TRACE_CACHE_KEY_PREFIX = "trace:cache:"
TRACE_CACHE_TTL_SECONDS = 5 * 60  # 5 minutes, per spec

# Returned trace payload schema (kept loose-typed for forward compat).
# {
#   "trace_id": str,
#   "source": "cache" | "db",
#   "events": [{"audit_id": int, "created_at": ISO 8601, "model": str,
#               "model_kind": str, "user_id": str, "workflow_id": str|None,
#               "upstream_status": int|None, "latency_ms": int,
#               "pii_redacted_count": int, "pii_detected_types": [str, ...],
#               "token_input": int|None, "token_output": int|None,
#               "error_class": str|None}],
# }


def _cache_key(trace_id: str) -> str:
    return f"{TRACE_CACHE_KEY_PREFIX}{trace_id}"


async def _read_cache(trace_id: str) -> dict | None:
    """Read the trace cache from Redis. Returns None on miss or error.

    The cache stores the full trace payload as JSON. Reading is
    best-effort: any Redis error is logged and treated as a miss
    so the L2 fallback can take over.
    """
    r = redis_client.get_redis()
    try:
        raw = await r.get(_cache_key(trace_id))
    except Exception as e:
        # Treat connection errors as miss (degrade to L2). Don't raise.
        logger.warning("trace cache read failed for %s: %s", trace_id, e)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        # Corrupted cache entry — log and treat as miss. L2 will repopulate.
        logger.warning("trace cache value for %s not valid JSON: %s", trace_id, e)
        return None


async def _write_cache(trace_id: str, payload: dict) -> None:
    """Write the trace cache to Redis. Best-effort — failure does not
    surface to the caller."""
    r = redis_client.get_redis()
    try:
        await r.set(
            _cache_key(trace_id),
            json.dumps(payload, default=str),
            ex=TRACE_CACHE_TTL_SECONDS,
        )
    except Exception as e:
        # L1 write is a perf optimization, not a correctness requirement.
        # The next read will re-fetch from L2 and try again.
        logger.warning("trace cache write failed for %s: %s", trace_id, e)


async def _read_db(trace_id: str) -> list[dict[str, Any]]:
    """Read the trace from the audit_log table. Returns an empty list
    if no rows match (caller turns that into 404)."""
    async with get_session() as s:
        stmt = (
            select(AuditLog)
            .where(AuditLog.trace_id == trace_id)
            .order_by(AuditLog.created_at.asc())
        )
        rows = (await s.execute(stmt)).scalars().all()
    return [
        {
            "audit_id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "model": r.model,
            "model_kind": r.model_kind,
            "user_id": r.user_id,
            "workflow_id": r.workflow_id,
            "upstream_status": r.upstream_status,
            "latency_ms": r.latency_ms,
            "pii_redacted_count": r.pii_redacted_count,
            "pii_detected_types": list(r.pii_detected_types or []),
            "token_input": r.token_input,
            "token_output": r.token_output,
            "error_class": r.error_class,
        }
        for r in rows
    ]


@router.get("/{trace_id}")
async def get_trace(
    trace_id: str = Path(..., min_length=8, max_length=128),
) -> dict:
    """Read a single trace's audit history.

    Returns the trace payload, including the source of the read
    (``"cache"`` or ``"db"``) so callers can tell which tier served
    the request. 404 if both tiers miss.
    """
    # L1: Redis cache
    cached = await _read_cache(trace_id)
    if cached is not None:
        # Mark the source on the response. The cache stores the events
        # list verbatim, so we just stamp the source.
        cached["source"] = "cache"
        return cached

    # L2: Postgres audit_log
    events = await _read_db(trace_id)
    if not events:
        raise HTTPException(status_code=404, detail=f"trace {trace_id!r} not found")

    payload = {
        "trace_id": trace_id,
        "source": "db",
        "events": events,
    }
    # Populate L1 so the next call hits the cache. Best-effort.
    await _write_cache(trace_id, payload)
    return payload


__all__ = ["router", "TRACE_CACHE_KEY_PREFIX", "TRACE_CACHE_TTL_SECONDS"]
