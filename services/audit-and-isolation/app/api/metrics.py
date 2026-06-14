"""GET /metrics — Prometheus text exposition format.

Per task 5.2 of `openspec/changes/gateway-egress-enforcement-p0/`.
The endpoint serves the live state of the 5 metrics defined in
``app/metrics.py`` (V6b group):

  * ``requests_total{method,path,status}``      — Counter
  * ``duration_seconds_bucket``                  — Histogram
  * ``pii_hits_total{pii_type,action}``         — Counter
  * ``active_connections``                       — Gauge
  * ``trace_cache_hits_total``                   — Counter

Format spec: https://prometheus.io/docs/instrumenting/exposition_formats/
The response is plain text (Content-Type ``text/plain; version=0.0.4``)
and includes ``HELP`` and ``TYPE`` comment lines for each metric, so
the scraper can render the metrics without a separate schema.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.metrics import METRICS_CONTENT_TYPE, render_metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def get_metrics() -> Response:
    """Return the Prometheus text exposition of the current metrics.

    Prometheus scrapes this every ~15s. The endpoint is cheap
    (just serializes the in-process counters); no I/O, no auth
    (relies on the k8s NetworkPolicy / Service Mesh to restrict
    who can reach it).
    """
    return Response(
        content=render_metrics(),
        media_type=METRICS_CONTENT_TYPE,
    )


__all__ = ["router"]
