"""Performance contracts — Protocol + Noop default implementations.

Per task 5.1 of `openspec/changes/gateway-egress-enforcement-p0/`. The
chat endpoint (and any other request-handling code) needs four pluggable
performance primitives, each with a Protocol (the interface) and a
Noop default (the safe-but-doesn't-do-anything implementation):

  * **RateLimiter**        — "should I let this request through?"
  * **ResponseCache**       — "have I seen this exact request before?"
  * **RequestBatcher**     — "can I group this with other in-flight requests?"
  * **MetricsExporter**    — "publish a number for ops/monitoring"

The design follows the same pattern used elsewhere in the gateway
(`app/redis_client.get_redis()` for a swappable Redis, etc.):
production code injects a real implementation at lifespan startup;
tests inject fakes; the Noop is the safe fallback when nothing is
configured.

Why Protocol + Noop rather than concrete classes?
--------------------------------------------------

1. **Substitutability** — PEP 544 structural subtyping lets any class
   with the right methods satisfy the Protocol without inheriting
   from a base class. This means a future swap to a third-party
   library (e.g. `aiocache` for ResponseCache) doesn't require a
   wrapper class.

2. **Test-friendly** — Tests can pass lightweight stubs (e.g. a
   counter that just increments) without instantiating the full
   implementation hierarchy.

3. **Default safety** — If the lifespan forgets to wire a real
   implementation, the Noop is the safest fallback: the request
   goes through, no metrics are dropped (the Noop records them
   but does nothing), no rate limit is enforced, no cache hit
   is served. The "missing" behaviour is observable (operators
   see "no metrics in Prometheus" / "no cache hit rate in logs")
   but not dangerous.

Where the contracts are called from
------------------------------------

These are *not* called yet. The chat endpoint (5.3) will integrate
them at the four canonical points:

  1. RateLimiter.check(user_id, model) before calling upstream
  2. ResponseCache.get(request_hash) before parsing the body
  3. RequestBatcher.submit(request) when multiple requests for the
     same model arrive within the batch window
  4. MetricsExporter.observe_*(...) at every transition point

5.3 is the integration task; this task (5.1) is the interface
definition and the noop fallback that makes 5.3 testable in
isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol, runtime_checkable


# =============================================================================
# RateLimiter
# =============================================================================


@runtime_checkable
class RateLimiter(Protocol):
    """Decide whether a request is allowed to proceed.

    The interface is intentionally minimal — a single ``check`` that
    takes the user identity and the target model. Concrete
    implementations decide what to do with this (token bucket,
    sliding window, fixed quota, etc.).
    """

    def check(self, user_id: str, model: str) -> bool:
        """Return True if the request is allowed, False if rate-limited.

        The check is **synchronous** because we want to fail fast on
        a 429-equivalent without spinning up an event loop. If a
        remote-system implementation is needed, the Noop is the
        fallback for tests and dev.
        """
        ...


class NoopRateLimiter:
    """A rate limiter that never limits anything.

    All requests are allowed. Use this in dev and tests where the
    real rate limiter is either not configured or the test
    explicitly wants to disable it.
    """

    def check(self, user_id: str, model: str) -> bool:
        return True


# =============================================================================
# ResponseCache
# =============================================================================


@runtime_checkable
class ResponseCache(Protocol):
    """Cache upstream LLM responses keyed by request hash.

    The cache is **content-addressed** by the request hash (the same
    hash used by the audit_log.prompt_hash column). This makes
    dedup-by-prompt possible — the same prompt sent twice in 5
    minutes returns the cached response on the second call, saving
    upstream tokens and latency.
    """

    def get(self, request_hash: str) -> Any | None:
        """Return the cached response (any JSON-serializable), or None
        if the key isn't cached or has expired."""
        ...

    def put(self, request_hash: str, response: Any, ttl_seconds: int) -> None:
        """Store ``response`` under ``request_hash`` for ``ttl_seconds``.

        The TTL is per-call rather than a global setting because
        some prompts are short-lived (e.g. live data lookups) and
        others can be cached for minutes (e.g. a static FAQ).
        """


class NoopResponseCache:
    """A cache that never returns a hit and never stores anything.

    Reads always miss; writes are silently dropped. Use in dev/test
    when caching should not interfere with assertions.
    """

    def get(self, request_hash: str) -> Any | None:
        return None

    def put(self, request_hash: str, response: Any, ttl_seconds: int) -> None:
        # Deliberately a no-op: the spec says Noop is "safe but
        # doesn't do anything". Operators can detect "no cache hits
        # in logs" as a sign the real cache isn't wired up.
        return None


# =============================================================================
# RequestBatcher
# =============================================================================


@runtime_checkable
class RequestBatcher(Protocol):
    """Group concurrent identical requests into one upstream call.

    When two requests with the same key arrive within a small window
    (typically 50-200ms), the second request attaches to the first
    one's upstream future instead of issuing its own. This is a
    common pattern in LLM gateways: the same prompt from two
    browser tabs deduplicates into a single upstream call.

    The interface is a single ``submit`` that returns a Future
    (asyncio.Future) that resolves with the upstream response. The
    caller awaits the future just like it would await a direct
    upstream call.
    """

    def submit(
        self, key: str, request: Any
    ) -> "asyncio.Future[Any]":  # type: ignore[name-defined]  # noqa: F821
        """Submit a request for batching.

        ``key`` is the dedup key (typically request_hash). If another
        caller has already submitted a request with the same key
        and it's still in-flight, the returned future is shared —
        both callers see the same result when it resolves.

        ``request`` is opaque to the batcher; it gets passed through
        to the upstream when the batch is flushed.
        """
        ...


class NoopRequestBatcher:
    """A batcher that never batches anything.

    Each call returns a never-resolved future — so any caller that
    awaits it will hang. The chat endpoint must NOT use the
    NoopRequestBatcher in production; this is a placeholder for
    tests that don't exercise the batching path.
    """

    def submit(self, key: str, request: Any) -> "NoopBatcherFuture":
        # Return a never-resolved future so callers that await it
        # immediately see the broken contract in tests.
        fut: Any = _NeverResolvedFuture()
        return fut  # type: ignore[return-value]


class _NeverResolvedFuture:
    """A future that never resolves, returned by NoopRequestBatcher.

    Awaiting it would block forever. Tests that use NoopRequestBatcher
    must NOT await the future; the contract violation is the point.
    """

    def done(self) -> bool:
        return False

    def result(self) -> Any:
        raise RuntimeError("NoopRequestBatcher never resolves — use a real batcher")

    def __await__(self):
        # Yielding forever to make the broken contract visible.
        import asyncio
        self._never = asyncio.Event()
        return self._never.__await__()


# Workaround: _NeverResolvedFuture isn't actually a real asyncio.Future,
# but the type hint in the Protocol is asyncio.Future. Tests should
# not await NoopRequestBatcher.submit(); they should check the
# *type* of the returned object. The NoopBatcherFuture type alias
# documents the real return type.
NoopBatcherFuture = _NeverResolvedFuture


# =============================================================================
# MetricsExporter
# =============================================================================


@runtime_checkable
class MetricsExporter(Protocol):
    """Publish per-request metrics for Prometheus.

    The interface is **five methods** (one per spec 5.2 metric family).
    Each method corresponds to one metric in the ``/metrics``
    endpoint. Concrete implementations typically use the
    ``prometheus_client`` library; the Noop records nothing.

    Method names are short and verb-form to keep call sites readable
    (``metrics.observe_request("POST", "/v1/chat", 200)``).
    """

    def observe_request(self, method: str, path: str, status: int) -> None:
        """Counter: requests_total{method, path, status}.

        Called once per HTTP request that reaches the gateway.
        ``status`` is the HTTP status code returned (or 0 if the
        request never produced a response, e.g. dropped mid-flight).
        """
        ...

    def observe_duration(self, seconds: float) -> None:
        """Histogram: duration_seconds_bucket.

        Called once per request, after the response is generated.
        The histogram buckets are implementation-defined (Noop has
        none).
        """

    def observe_pii_hit(self, pii_type: str, action: str) -> None:
        """Counter: pii_hits_total{pii_type, action}.

        Called each time a PII rule fires. ``action`` is one of
        ``redact`` / ``reverse`` / ``detect``.
        """

    def set_active_connections(self, count: int) -> None:
        """Gauge: active_connections.

        Called periodically (e.g. in the FastAPI lifespan) with the
        current connection count from the httpx pool.
        """

    def observe_trace_cache_hit(self) -> None:
        """Counter: trace_cache_hits_total.

        Called each time the L1 trace cache (4.1) returns a hit
        without falling through to PG.
        """


class NoopMetricsExporter:
    """A metrics exporter that drops everything on the floor.

    All methods are no-ops. Use in dev/test where the real
    prometheus_client wiring would be overkill. Operators detect
    "missing metrics in Prometheus" as the symptom of forgetting
    to wire the real exporter.
    """

    def observe_request(self, method: str, path: str, status: int) -> None:
        return None

    def observe_duration(self, seconds: float) -> None:
        return None

    def observe_pii_hit(self, pii_type: str, action: str) -> None:
        return None

    def set_active_connections(self, count: int) -> None:
        return None

    def observe_trace_cache_hit(self) -> None:
        return None


# =============================================================================
# Module exports
# =============================================================================

__all__ = [
    "MetricsExporter",
    "NoopBatcherFuture",
    "NoopMetricsExporter",
    "NoopRateLimiter",
    "NoopRequestBatcher",
    "NoopResponseCache",
    "RateLimiter",
    "RequestBatcher",
    "ResponseCache",
]
