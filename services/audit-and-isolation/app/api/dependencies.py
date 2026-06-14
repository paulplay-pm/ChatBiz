"""Per-request dependency injection for the 4 perf contracts.

Per task 5.3 of `openspec/changes/gateway-egress-enforcement-p0/`. The
chat endpoint reads its rate-limiter, response-cache, request-batcher,
and metrics-exporter from ``app.state``, which the lifespan populates
at startup. In dev / tests the lifespan uses the Noop defaults, so the
chat endpoint stays functional even when the real impls aren't wired
up.

The dependency getters here are the **only** way the chat endpoint
should access these contracts. Avoid direct ``import`` of the Noop
classes from chat code — going through ``request.app.state`` keeps
the test injection pattern uniform.
"""

from __future__ import annotations

from fastapi import Request

from app.perf import (
    MetricsExporter,
    NoopMetricsExporter,
    NoopRateLimiter,
    NoopRequestBatcher,
    NoopResponseCache,
    RateLimiter,
    RequestBatcher,
    ResponseCache,
)


# State-attribute names. Centralised so refactors don't leave
# dangling string references in chat.py.
STATE_RATE_LIMITER = "rate_limiter"
STATE_RESPONSE_CACHE = "response_cache"
STATE_REQUEST_BATCHER = "request_batcher"
STATE_METRICS = "metrics"


def get_rate_limiter(request: Request) -> RateLimiter:
    """Return the rate limiter instance wired in app.state.

    Falls back to NoopRateLimiter if the lifespan never set the
    state attribute. This fallback is what makes dev-mode (no
    wiring) work without raising AttributeError on every request.
    """
    return getattr(request.app.state, STATE_RATE_LIMITER, NoopRateLimiter())


def get_response_cache(request: Request) -> ResponseCache:
    return getattr(request.app.state, STATE_RESPONSE_CACHE, NoopResponseCache())


def get_request_batcher(request: Request) -> RequestBatcher:
    return getattr(request.app.state, STATE_REQUEST_BATCHER, NoopRequestBatcher())


def get_metrics(request: Request) -> MetricsExporter:
    return getattr(request.app.state, STATE_METRICS, NoopMetricsExporter())


__all__ = [
    "STATE_METRICS",
    "STATE_RATE_LIMITER",
    "STATE_REQUEST_BATCHER",
    "STATE_RESPONSE_CACHE",
    "get_metrics",
    "get_rate_limiter",
    "get_request_batcher",
    "get_response_cache",
]
