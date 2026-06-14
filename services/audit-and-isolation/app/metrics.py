"""Prometheus counters + histograms + gauges for the audit-and-isolation service.

The metrics live in the same process as the gateway; in a 2-pod
HA deployment each pod exposes its own metrics on the
``/metrics`` endpoint (added in Phase 14 / task 5.2). The
Prometheus scrape config tags the two pods separately via the
``pod`` label.

Two groups of metrics:

  **V5a (existing)**: 4 counters + 1 histogram from the original
  chat-completion plan. Kept for backwards compatibility with
  existing dashboards; not deprecated because ops may still scrape
  them.

  **V6b (added task 5.2)**: 5 metrics from the perf contracts
  spec — ``requests_total``, ``duration_seconds_bucket``,
  ``pii_hits_total``, ``active_connections``, ``trace_cache_hits_total``.
  These are 1:1 with the five methods on the ``MetricsExporter``
  Protocol (``app/perf/contracts.py``). The 5.3 chat-endpoint
  integration will call them at the canonical 4 transition points;
  for now (5.2), they're registered but unreferenced — the
  /metrics endpoint simply reports 0 for any metric that hasn't
  been incremented yet.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# =============================================================================
# V5a (existing) — kept for backwards compatibility
# =============================================================================

pii_fail_open_counter = Counter(
    "pii_detector_fail_open_total",
    "PII detector failed open (passed through unredacted text)",
)

upstream_5xx_counter = Counter(
    "upstream_5xx_total",
    "Upstream 5xx responses (after one retry)",
)

redis_unavailable_counter = Counter(
    "redis_unavailable_total",
    "Redis unavailable events (pool exhausted or call failed in a hot path)",
)

credential_unavailable_counter = Counter(
    "credential_service_unavailable_total",
    "Credential service unavailable events (after one retry)",
)

# Note: V5a named this `gateway_latency_seconds`; V6b spec says
# `duration_seconds`. We keep the old name to avoid breaking
# existing scrapes, and add `duration_seconds` as the new canonical
# name for the 5.2 /metrics endpoint.
latency_histogram = Histogram(
    "gateway_latency_seconds",
    "Gateway layer latency (request received -> response sent)",
)

# =============================================================================
# V6b (task 5.2) — 5 metrics matching the MetricsExporter Protocol
# =============================================================================

requests_total = Counter(
    "requests_total",
    "Total HTTP requests handled by the gateway, labeled by method, path, and HTTP status",
    ["method", "path", "status"],
)

duration_seconds = Histogram(
    "duration_seconds",
    "Request handling latency in seconds (per request, from middleware entry to response)",
    # Buckets are 1ms to 10s — covers LLM streaming responses which
    # are 1-60s for chat completions. Tighter buckets near 1ms
    # so the SLO p99 = 50ms (per the upstream plan) is resolvable.
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

pii_hits_total = Counter(
    "pii_hits_total",
    "PII rule firings, labeled by the rule type and the action taken",
    ["pii_type", "action"],
)

active_connections = Gauge(
    "active_connections",
    "Number of currently-active outbound HTTP connections (sampled from the httpx pool)",
)

trace_cache_hits_total = Counter(
    "trace_cache_hits_total",
    "L1 trace cache (Redis) hits that did not fall through to PG (per task 4.1)",
)

# =============================================================================
# Helpers
# =============================================================================

# `prometheus_client.CONTENT_TYPE_LATEST` is the official Content-Type
# for Prometheus text exposition format. Re-exported so the API
# layer doesn't need to import prometheus_client directly.
METRICS_CONTENT_TYPE = CONTENT_TYPE_LATEST


def render_metrics() -> bytes:
    """Render the current Prometheus metrics snapshot as bytes.

    The /metrics endpoint calls this on every scrape. Returns
    bytes (not str) because FastAPI/Starlette prefers bytes for
    binary-safe response bodies, and ``generate_latest`` is
    already bytes.
    """
    return generate_latest()


__all__ = [
    # V5a
    "credential_unavailable_counter",
    "latency_histogram",
    "pii_fail_open_counter",
    "redis_unavailable_counter",
    "upstream_5xx_counter",
    # V6b — task 5.2
    "active_connections",
    "duration_seconds",
    "pii_hits_total",
    "requests_total",
    "trace_cache_hits_total",
    # Helpers
    "METRICS_CONTENT_TYPE",
    "render_metrics",
]
