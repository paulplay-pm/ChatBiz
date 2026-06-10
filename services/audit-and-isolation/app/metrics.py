"""Prometheus counters + histograms for the audit-and-isolation service.

These are referenced from the API layer (``chat.py``) at the
failure points called out in the plan. They are intentionally
minimal: just the four counters + one histogram the plan locks
in (Task 13.1-13.3).

The metrics live in the same process as the gateway; in a 2-pod
HA deployment each pod exposes its own metrics on the
``/metrics`` endpoint (added in Phase 14). The Prometheus scrape
config tags the two pods separately via the ``pod`` label.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

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


__all__ = [
    "credential_unavailable_counter",
    "latency_histogram",
    "pii_fail_open_counter",
    "redis_unavailable_counter",
    "upstream_5xx_counter",
]
