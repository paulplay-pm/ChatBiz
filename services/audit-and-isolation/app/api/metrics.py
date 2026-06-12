"""GET /metrics — Prometheus exposition endpoint.

Exposes the 5 metric families the Phase E perf contract spec
locks in (design D8 + spec.md Requirement: 必须暴露
``/metrics`` Prometheus 端点):

* ``chatbiz_gateway_requests_total{method,path,status}``
* ``chatbiz_gateway_request_duration_seconds_bucket{le,...}``
* ``chatbiz_gateway_pii_hits_total{pii_type,action}``
* ``chatbiz_gateway_active_connections`` (Gauge)
* ``chatbiz_gateway_trace_cache_hits_total``

Format: Prometheus text exposition format ``0.0.4`` —
``text/plain; version=0.0.4; charset=utf-8``. The
``prometheus_client`` library handles the rendering via
:func:`generate_latest`, which already emits ``# HELP`` and
``# TYPE`` comment lines for every registered metric (the
spec's "HELP + TYPE 注释存在" requirement).

Mounted on the app without a ``/v1`` prefix so a Prometheus
scraper can hit ``/metrics`` directly. The router is included
in :mod:`app.main`.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/metrics")
async def metrics() -> Response:
    """Return the current Prometheus exposition payload.

    The body is the serialised output of every metric registered
    in the default ``prometheus_client.REGISTRY``. The content
    type is taken from :data:`CONTENT_TYPE_LATEST` so the
    response carries the correct ``version=0.0.4`` parameter
    that Prometheus servers parse to pick the right parser.

    No body parsing, no I/O — the scrape path is intentionally
    cheap. The /metrics endpoint must never block on a
    dependency (PG, Redis, LLM upstream) because Prometheus
    scrapes on a fixed interval and a slow scrape makes the
    gateway look unhealthy.
    """
    payload = generate_latest()
    return Response(
        content=payload,
        media_type=CONTENT_TYPE_LATEST,
        status_code=200,
    )


__all__ = ["router"]
