"""Prometheus counters + histograms for the audit-and-isolation service.

These are referenced from the API layer (``chat.py``) at the
failure points called out in the plan. They are intentionally
minimal: just the four counters + one histogram the plan locks
in (Task 13.1-13.3).

The metrics live in the same process as the gateway; in a 2-pod
HA deployment each pod exposes its own metrics on the
``/metrics`` endpoint (added in Phase 14). The Prometheus scrape
config tags the two pods separately via the ``pod`` label.

The metrics added in Phase E (perf contracts + /metrics endpoint)
follow the spec locked in
``openspec/changes/gateway-egress-enforcement-p0/specs/gateway-perf-contracts/spec.md``
and ``design.md`` decision D8:

* ``chatbiz_gateway_requests_total{method,path,status}`` — total
  HTTP requests through the gateway, tagged by route.
* ``chatbiz_gateway_request_duration_seconds`` — histogram of
  request latencies.
* ``chatbiz_gateway_pii_hits_total{pii_type,action}`` — PII
  detections (action = "mask" | "fail_open" | "skip").
* ``chatbiz_gateway_active_connections`` — gauge of in-flight
  requests (incremented at the start of the chat pipeline,
  decremented on response).
* ``chatbiz_gateway_trace_cache_hits_total`` — counter for
  response cache hits (Phase E contract #2 — the actual cache
  implementation is delivered by T6; this counter is incremented
  on every cache hit).
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

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

latency_histogram = Histogram(
    "gateway_latency_seconds",
    "Gateway layer latency (request received -> response sent)",
)


# ---------------------------------------------------------------------------
# Phase E: /metrics exposition
# ---------------------------------------------------------------------------
# These are the 5 metric families the spec requires (D8). The names
# all start with the ``chatbiz_gateway_`` prefix so a Prometheus
# scrape can group them under one selector. The legacy counters
# above (no ``chatbiz_gateway_`` prefix) stay in place — they're
# referenced by the existing tests and ops dashboards.


gateway_requests_total = Counter(
    "chatbiz_gateway_requests_total",
    "Total HTTP requests handled by the gateway, labelled by method/path/status.",
    labelnames=("method", "path", "status"),
)

gateway_request_duration_seconds = Histogram(
    "chatbiz_gateway_request_duration_seconds",
    "End-to-end request duration in seconds (request received -> response sent).",
    labelnames=("method", "path"),
    # Default Prometheus buckets — good for a sub-second to
    # multi-second SLO surface. Override at scrape time if
    # tighter buckets are needed.
)

gateway_pii_hits_total = Counter(
    "chatbiz_gateway_pii_hits_total",
    "PII detections by the redactor, labelled by PII type and action.",
    labelnames=("pii_type", "action"),
)

gateway_active_connections = Gauge(
    "chatbiz_gateway_active_connections",
    "Number of in-flight HTTP requests currently being processed by the gateway.",
)

gateway_trace_cache_hits_total = Counter(
    "chatbiz_gateway_trace_cache_hits_total",
    "Number of response cache hits served without an upstream LLM call.",
)

# Contract degradation counter — incremented when a real (T6)
# perf contract implementation raises and the chat pipeline
# falls back to Noop behaviour. Keeping it here so the same
# /metrics scrape picks it up.
gateway_contract_degraded_total = Counter(
    "chatbiz_gateway_contract_degraded_total",
    "Times a perf contract raised an exception and the chat pipeline degraded to Noop.",
    labelnames=("contract",),
)


__all__ = [
    "credential_unavailable_counter",
    "gateway_active_connections",
    "gateway_contract_degraded_total",
    "gateway_pii_hits_total",
    "gateway_request_duration_seconds",
    "gateway_requests_total",
    "gateway_trace_cache_hits_total",
    "latency_histogram",
    "pii_fail_open_counter",
    "redis_unavailable_counter",
    "upstream_5xx_counter",
]

