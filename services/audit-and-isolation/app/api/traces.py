"""Cross-instance trace query endpoint.

Implements ``GET /v1/traces/{trace_id}`` per spec at
``openspec/changes/gateway-egress-enforcement-p0/specs/
gateway-trace-cross-instance-query/spec.md``:

* Redis (trace:cache:*, db 0, 5min TTL) hit → return immediately,
  P99 < 100ms. Header ``X-Trace-Source: redis``.
* PG ``audit_log`` hit → return events, re-cache in Redis 5min.
  P99 < 500ms. Header ``X-Trace-Source: pg``.
* Both miss → 404 with ``{"error": "trace_not_found", ...}``.

The store instance is created lazily on first call to
``get_trace_store()`` so importing this module doesn't open any
connection. The factory uses the real ``app.redis_client.get_redis``
+ ``app.database._get_session_factory`` — tests can replace the
module-level ``_store`` directly via :func:`set_trace_store` (or the
``override_store`` fixture helper).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Response

from app.database import _get_session_factory
from app.redis_client import get_redis
from app.trace.store import (
    SOURCE_HIT_PG,
    SOURCE_HIT_REDIS,
    TraceStore,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level singleton — replaced by tests via set_trace_store().
_store: TraceStore | None = None


def get_trace_store() -> TraceStore:
    """Return the process-wide :class:`TraceStore`.

    Lazy init: the first call builds the store from the live Redis
    client + the cached session factory. Subsequent calls reuse the
    same instance.
    """
    global _store
    if _store is None:
        _store = TraceStore(
            redis_client=get_redis(),
            session_factory=_get_session_factory(),
        )
    return _store


def set_trace_store(store: TraceStore | None) -> None:
    """Replace the module-level store. Test-only."""
    global _store
    _store = store


def reset_store_for_tests() -> None:
    """Drop the cached store. Test-only helper."""
    global _store
    _store = None


@router.get("/v1/traces/{trace_id}")
async def get_trace(trace_id: str, response: Response) -> dict:
    """Return all audit events for ``trace_id``.

    Always returns 200 with an empty list and source ``pg`` if the
    trace is genuinely unknown, OR 404 with ``trace_not_found`` —
    the spec mandates 404 for the miss case, so we use the latter.
    """
    store = get_trace_store()
    events, source = await store.get(trace_id)
    if not events:
        # Per spec: 404, error body. The X-Trace-Source header is
        # omitted because there is no source — both stores missed.
        response.status_code = 404
        return {"error": "trace_not_found", "trace_id": trace_id}
    response.headers["X-Trace-Source"] = source
    return {
        "trace_id": trace_id,
        "events": events,
    }


__all__ = [
    "get_trace_store",
    "reset_store_for_tests",
    "router",
    "set_trace_store",
]
