"""4 perf contract Protocols + Noop default implementations.

These are the extension points for T6 (the future performance spec
that delivers real rate limiting, response caching, request
batching, and metrics export). The Protocols are intentionally
narrow — they describe *what* the chat pipeline needs from each
optimization, not *how* it should be implemented (Redis? in-process
LRU? batched via asyncio.gather?). T6 picks the backend.

Contract summary (from eng-review Perf #1 / design D7):

* :class:`RateLimiter` — token-bucket style gate that the chat
  pipeline calls after auth. When the limiter returns ``False``
  the chat endpoint returns HTTP 429. Noop always returns ``True``
  so the pipeline is never blocked when no limiter is configured.

* :class:`ResponseCache` — hash-keyed response store. The chat
  pipeline calls :meth:`get` before doing any upstream work, and
  :meth:`put` after a successful upstream call. Noop is a sink —
  get always returns ``None``, put discards the value.

* :class:`RequestBatcher` — coalesces concurrent upstream calls
  into a single request. T6 may merge 3 in-flight chat calls into
  one upstream POST and dispatch the 3 response bodies back to the
  3 waiting futures. Noop executes the call synchronously
  (the returned ``Future`` is already resolved with the
  ``Response``).

* :class:`MetricsExporter` — a pluggable sink for internal
  metrics. The chat pipeline calls :meth:`export` to push a
  :class:`Metric` sample. Noop accepts the call but doesn't
  publish anywhere (the Prometheus ``/metrics`` endpoint reads
  the global ``prometheus_client.REGISTRY`` directly, so this
  contract is reserved for *out-of-process* sinks that T6 may
  add later, e.g. an OTLP exporter).

Failure-degradation contract:

Each Noop is also the *degradation target* for its Protocol.
When the real implementation raises (Redis down, batcher
timeout, exporter 5xx), the chat pipeline catches the exception
and falls back to the Noop behaviour for that single call. The
fallback is recorded via a Prometheus counter
``contract_degraded{contract="..."}`` added in the chat pipeline
(not in this module — keeping the perf package I/O free).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CachedResponse:
    """A serialised upstream response stored in the response cache.

    Frozen so an entry cannot be mutated after it's been put; the
    cache key is computed by the chat pipeline (``request_hash``),
    not here, so a single key can be safely read by multiple
    concurrent goroutines.
    """

    body: bytes
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Request:
    """The minimal envelope the batcher needs to coalesce calls.

    The chat pipeline populates the fields that affect coalescing
    decisions (``model`` + the OpenAI-shaped body) and the
    batcher uses them to decide whether two calls can share an
    upstream POST. Noop ignores the fields and just calls the
    underlying upstream directly.
    """

    model: str
    body: dict[str, Any]
    headers: dict[str, str]


@dataclass(frozen=True)
class Response:
    """A response object the batcher hands back via the ``Future``.

    The chat pipeline treats this the same as the
    ``httpx.Response`` it currently gets from :func:`call_upstream`
    — the pipeline only reads ``status_code`` and ``json()`` /
    ``text``, both of which we expose as methods.
    """

    status_code: int
    body: dict[str, Any]

    def json(self) -> dict[str, Any]:
        return self.body


@dataclass(frozen=True)
class Metric:
    """A single metric sample, expressed in the Prometheus data model.

    ``name`` is the metric base name (no labels), ``labels`` is the
    label dict, and ``value`` is the sample value. ``kind`` tells
    the exporter whether to treat the value as a counter increment
    (counter), a gauge update (gauge), or a histogram observation
    (histogram).
    """

    name: str
    value: float
    kind: str  # "counter" | "gauge" | "histogram"
    labels: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class RateLimiter(Protocol):
    """Token-bucket style gate.

    The chat pipeline calls this after auth. Implementations may
    keep per-user / per-model buckets in Redis (T6) or in-process
    (T6's per-pod fallback). The protocol is deliberately
    synchronous — the rate-limit decision has to be O(1) on the
    hot path.
    """

    def check(self, user_id: str, model: str) -> bool:
        """Return ``True`` if the request may proceed, ``False`` otherwise.

        A ``False`` return causes the chat endpoint to short-circuit
        with HTTP 429 + ``{"error": "rate_limited", "retry_after": N}``
        — the ``N`` value is decided by the implementation (the
        pipeline doesn't compute a retry budget itself).
        """
        ...


@runtime_checkable
class ResponseCache(Protocol):
    """Hash-keyed response store.

    The chat pipeline computes ``request_hash = sha256(model + body)``
    and looks it up before the upstream call. A hit returns the
    cached body verbatim (after PII scanning — the pipeline owns
    that step, the cache is content-agnostic).
    """

    def get(self, request_hash: str) -> Optional[CachedResponse]:
        """Return the cached entry or ``None`` on miss."""
        ...

    def put(self, request_hash: str, response: CachedResponse, ttl: int) -> None:
        """Store ``response`` under ``request_hash`` for ``ttl`` seconds.

        ``ttl`` is a hint; implementations are free to evict earlier
        (LRU) or later (no expiry). Noop discards the call.
        """
        ...


@runtime_checkable
class RequestBatcher(Protocol):
    """Coalesces concurrent upstream calls.

    T6's real implementation may merge 3 simultaneous
    ``Request``s into a single upstream POST and return 3
    ``Response``s that get dispatched into the 3 ``Future``s
    (see spec scenario "批量合并"). Noop just runs the upstream
    call synchronously and resolves the future immediately.
    """

    def submit(self, request: Request) -> asyncio.Future[Response]:
        """Submit a request; return a future that resolves to the response.

        The future **must** be an ``asyncio.Future`` (not a
        ``concurrent.futures.Future``) so the chat pipeline can
        ``await`` it without bridging executors.
        """
        ...


@runtime_checkable
class MetricsExporter(Protocol):
    """Pluggable sink for metrics that don't fit the default
    ``prometheus_client.REGISTRY`` path.

    The chat pipeline uses this for cross-cutting signals
    (contract degradation, trace cache hit/miss) that T6 may want
    to forward to a non-Prometheus backend (OTLP, StatsD, etc.).
    """

    def export(self, metric: Metric) -> None:
        """Publish ``metric``. Implementations are expected to
        not raise on transport errors — they should swallow + log
        so the chat pipeline never blocks on metrics I/O."""
        ...


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _create_future() -> asyncio.Future[Response]:
    """Build a Future bound to the running loop.

    Always uses :func:`asyncio.get_running_loop` — the chat
    pipeline only ever calls :meth:`submit` from inside an
    async request handler, so a running loop is guaranteed. A
    synchronous caller that needs a future outside an event
    loop can wrap this in :func:`asyncio.run_coroutine_threadsafe`
    or use :func:`asyncio.get_event_loop` (deprecated but
    available).
    """
    loop = asyncio.get_running_loop()
    return loop.create_future()


def _schedule_coroutine(
    future: asyncio.Future[Response], coro: Any
) -> None:
    """Schedule ``coro`` on the running loop and bridge its result
    onto ``future``.

    Mirrors the coroutine branch of the original Noop's
    ``submit()``; factored out so both the Noop's hot path and
    the test fixtures can share it.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No loop — should be unreachable from the chat pipeline,
        # but if it happens we surface the failure on the future
        # rather than swallowing it.
        future.set_exception(
            RuntimeError("coroutine result with no running loop")
        )
        return
    task = loop.create_task(coro)

    def _resolve(_task: asyncio.Task) -> None:
        try:
            resp = _task.result()
            future.set_result(_to_response(resp))
        except Exception as exc:  # noqa: BLE001
            future.set_exception(exc)

    task.add_done_callback(_resolve)


# ---------------------------------------------------------------------------
# Noop defaults
# ---------------------------------------------------------------------------


class NoopRateLimiter:
    """Default :class:`RateLimiter` that never blocks a request.

    Used when the deployment has no real rate limiter configured
    (T6 has not landed) and as the degradation target when a
    real limiter raises an exception.
    """

    def check(self, user_id: str, model: str) -> bool:
        return True


class NoopResponseCache:
    """Default :class:`ResponseCache` that never hits and never stores.

    :meth:`get` always returns ``None`` (every request misses the
    cache, so the pipeline always does the full upstream work).
    :meth:`put` accepts the call and discards — the return type
    is ``None`` to match the Protocol.
    """

    def get(self, request_hash: str) -> Optional[CachedResponse]:
        return None

    def put(self, request_hash: str, response: CachedResponse, ttl: int) -> None:
        return None


class NoopRequestBatcher:
    """Default :class:`RequestBatcher` that runs each request synchronously.

    The :meth:`submit` method takes a ``Request``, executes the
    upstream call immediately (via a callable injected at
    construction time — keeps the Noop free of HTTP / LLM
    dependencies), and resolves the returned future with the
    response. The chat pipeline can ``await`` the future as if
    it were a normal ``asyncio.Future``.
    """

    def __init__(self, executor: Any = None) -> None:
        # ``executor`` is intentionally typed ``Any`` so tests can
        # inject a stub without importing ``call_upstream`` (which
        # would drag in the LLM client at module-import time). The
        # production wiring in ``app/api/chat.py`` passes
        # ``call_upstream`` here.
        self._executor = executor

    def submit(self, request: Request) -> asyncio.Future[Response]:
        """Run the request synchronously and resolve the future.

        The Noop path is fully synchronous — there's no real
        batching to wait for. We still return a ``Future`` (vs a
        plain ``Response``) so the chat pipeline's call site is
        identical between Noop and the T6 real implementation.
        """
        future: asyncio.Future[Response] = _create_future()
        if self._executor is None:
            # Defensive: when no executor is wired (e.g. unit
            # tests of the Noop in isolation), mark the future
            # done with an empty 200 so ``await`` doesn't hang.
            future.set_result(Response(status_code=200, body={}))
            return future
        try:
            result = self._executor(
                request.body.get("_base_url", ""),
                request.body.get("_path", ""),
                request.body,
                request.headers,
            )
        except Exception as exc:  # noqa: BLE001 — propagate to caller via future
            future.set_exception(exc)
            return future
        # The executor may be a coroutine — check the type to
        # decide whether to await it or use it directly.
        if asyncio.iscoroutine(result):
            _schedule_coroutine(future, result)
        else:
            future.set_result(_to_response(result))
        return future


def _to_response(raw: Any) -> Response:
    """Coerce an executor return value to a :class:`Response`.

    The executor is typically an ``httpx.Response`` (the real
    ``call_upstream``), but Noop tests may return anything that
    has ``status_code`` + ``json()`` or a plain ``Response``.
    """
    if isinstance(raw, Response):
        return raw
    status_code = getattr(raw, "status_code", 200)
    json_method = getattr(raw, "json", None)
    if callable(json_method):
        body = json_method()
    elif isinstance(raw, dict):
        body = raw
    else:
        body = {}
    return Response(status_code=int(status_code), body=body)


class NoopMetricsExporter:
    """Default :class:`MetricsExporter` that accepts but discards.

    Metrics that need a real sink go to the Prometheus
    ``/metrics`` endpoint directly; this Noop is reserved for
    the *out-of-process* sinks T6 may add later.
    """

    def export(self, metric: Metric) -> None:
        return None


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
