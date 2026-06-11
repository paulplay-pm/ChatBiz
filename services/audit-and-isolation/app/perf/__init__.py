"""Performance contracts for the audit-and-isolation gateway.

Defines the 4 perf Protocol interfaces that T6 (the future performance
optimization spec) will fill in with real implementations
(Redis-backed rate limiter, response cache, request batcher, and a
Prometheus exporter). For now this module ships only the Protocol
signatures and Noop defaults so the chat pipeline can be wired up
without blocking on T6.

Eng-review Perf #1 (locked-in decision D7) + D8 in
``openspec/changes/gateway-egress-enforcement-p0/design.md``.
"""

from app.perf.contracts import (
    CachedResponse,
    Metric,
    MetricsExporter,
    NoopMetricsExporter,
    NoopRateLimiter,
    NoopRequestBatcher,
    NoopResponseCache,
    RateLimiter,
    Request,
    RequestBatcher,
    Response,
    ResponseCache,
)

__all__ = [
    "CachedResponse",
    "Metric",
    "MetricsExporter",
    "NoopMetricsExporter",
    "NoopRateLimiter",
    "NoopRequestBatcher",
    "NoopResponseCache",
    "RateLimiter",
    "Request",
    "RequestBatcher",
    "Response",
    "ResponseCache",
]
