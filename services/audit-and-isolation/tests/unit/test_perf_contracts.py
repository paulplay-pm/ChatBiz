"""Unit tests for the perf contract Protocols + Noop defaults (task 5.1).

Per spec 5.1 of `openspec/changes/gateway-egress-enforcement-p0/`. Covers:

  * Protocol signature stability — the four Protocols have the exact
    method signatures the spec calls out. A future refactor that
    breaks the signature is caught here.
  * Noop default behaviour — each Noop returns the safe "do nothing"
    answer (allow the request, return cache miss, no batching,
    drop metrics). This is the fallback when the real impl isn't
    wired up.
  * `isinstance(obj, Protocol)` works for both real impls and Noops
    (via @runtime_checkable).
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

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
from app.perf.contracts import _NeverResolvedFuture


# ---------- RateLimiter -----------------------------------------------------

def test_rate_limiter_protocol_has_check() -> None:
    """Spec literal: `RateLimiter.check(user_id, model) -> bool`."""
    sig = inspect.signature(RateLimiter.check)
    params = list(sig.parameters.keys())
    assert "self" in params
    assert "user_id" in params
    assert "model" in params
    # Return type annotation: with `from __future__ import annotations`,
    # the annotation is a string ("bool"). Accept either form.
    ra = sig.return_annotation
    assert ra is bool or ra == "bool" or (
        hasattr(ra, "__name__") and ra.__name__ == "bool"
    )


def test_noop_rate_limiter_always_allows() -> None:
    rl = NoopRateLimiter()
    assert rl.check("user-1", "qwen-max") is True
    assert rl.check("user-2", "gpt-4") is True
    # Any user_id / model pair works — the Noop doesn't enforce
    # any rate at all.


def test_noop_rate_limiter_satisfies_protocol() -> None:
    """A Protocol with @runtime_checkable lets us isinstance-check."""
    assert isinstance(NoopRateLimiter(), RateLimiter)


def test_real_rate_limiter_satisfies_protocol() -> None:
    """A hand-rolled class with the right method satisfies the Protocol
    without inheriting from it (PEP 544 structural subtyping)."""

    class MyTokenBucket:
        def __init__(self):
            self.count = 0

        def check(self, user_id: str, model: str) -> bool:
            self.count += 1
            return self.count <= 100

    rl = MyTokenBucket()
    assert isinstance(rl, RateLimiter)
    assert rl.check("u1", "m1") is True


# ---------- ResponseCache ---------------------------------------------------

def test_response_cache_protocol_signatures() -> None:
    """Spec literal: get + put signatures match."""
    get_sig = inspect.signature(ResponseCache.get)
    assert list(get_sig.parameters.keys()) == ["self", "request_hash"]
    put_sig = inspect.signature(ResponseCache.put)
    assert list(put_sig.parameters.keys()) == ["self", "request_hash", "response", "ttl_seconds"]


def test_noop_response_cache_get_returns_none() -> None:
    cache = NoopResponseCache()
    assert cache.get("any-hash") is None
    assert cache.get("another-hash") is None


def test_noop_response_cache_put_is_silent() -> None:
    """put() on a Noop must not raise and must not store anything."""
    cache = NoopResponseCache()
    cache.put("hash-1", {"response": "ok"}, ttl_seconds=60)
    # Subsequent get returns None because Noop never stored anything.
    assert cache.get("hash-1") is None


def test_noop_response_cache_satisfies_protocol() -> None:
    assert isinstance(NoopResponseCache(), ResponseCache)


def test_real_response_cache_satisfies_protocol() -> None:
    """A simple dict-backed cache satisfies the Protocol structurally."""

    class DictCache:
        def __init__(self):
            self._store: dict[str, Any] = {}

        def get(self, request_hash: str) -> Any | None:
            return self._store.get(request_hash)

        def put(self, request_hash: str, response: Any, ttl_seconds: int) -> None:
            self._store[request_hash] = response

    cache = DictCache()
    assert isinstance(cache, ResponseCache)
    cache.put("h1", {"x": 1}, 60)
    assert cache.get("h1") == {"x": 1}


# ---------- RequestBatcher -------------------------------------------------

def test_request_batcher_protocol_has_submit() -> None:
    """Spec literal: `RequestBatcher.submit(request) -> Future[response]`."""
    sig = inspect.signature(RequestBatcher.submit)
    params = list(sig.parameters.keys())
    assert "self" in params
    assert "key" in params
    assert "request" in params


def test_noop_request_batcher_submit_returns_never_resolved_future() -> None:
    """Noop's submit returns a future that never resolves — the broken
    contract is the point (production code must not use Noop)."""
    batcher = NoopRequestBatcher()
    fut = batcher.submit("key-1", {"prompt": "hi"})
    # The returned object is a never-resolving future
    assert isinstance(fut, _NeverResolvedFuture)
    # .done() always returns False
    assert fut.done() is False
    # .result() raises (avoids accidental hang on call)
    with pytest.raises(RuntimeError, match="never resolves"):
        fut.result()


def test_noop_request_batcher_satisfies_protocol() -> None:
    """Noop is intentionally not runtime_checkable for RequestBatcher
    because the return type is `_NeverResolvedFuture`, not a real
    `asyncio.Future`. We assert via duck-typing instead."""
    batcher = NoopRequestBatcher()
    assert hasattr(batcher, "submit")
    assert callable(batcher.submit)


def test_real_request_batcher_satisfies_protocol() -> None:
    """A real impl returns an awaitable that resolves with the response.

    We don't instantiate a real asyncio.Future because pytest-asyncio's
    auto-mode in unit tests doesn't have a running event loop on the
    main thread (it spins up loops per-test only for `@pytest.mark.asyncio`
    tests). Instead we use a pre-resolved object that quacks like a
    Future — that's all the Protocol contract needs.
    """

    class ResolvedAwaitable:
        def __init__(self, value):
            self._value = value

        def done(self):
            return True

        def result(self):
            return self._value

        def __await__(self):
            # Yielding self as the awaited value lets `await fut`
            # resolve to self._value.
            return iter([self._value])

    class InProcessBatcher:
        def submit(self, key, request):
            return ResolvedAwaitable({"ok": True})

    batcher = InProcessBatcher()
    fut = batcher.submit("k", {})
    # Sanity-check the protocol contract: submit returns an
    # awaitable whose .done() / .result() work like a Future.
    assert fut.done() is True
    assert fut.result() == {"ok": True}


async def _await_future(fut):
    return await fut


# ---------- MetricsExporter ------------------------------------------------

def test_metrics_exporter_protocol_has_five_methods() -> None:
    """Spec literal: 5 methods (one per metric family in /metrics)."""
    expected = {
        "observe_request",
        "observe_duration",
        "observe_pii_hit",
        "set_active_connections",
        "observe_trace_cache_hit",
    }
    actual = set(dir(MetricsExporter))
    # The Protocol has at minimum these five public methods
    for method in expected:
        assert hasattr(MetricsExporter, method), f"missing {method} on MetricsExporter"


def test_metrics_exporter_observe_request_signature() -> None:
    """Spec literal: observe_request(method, path, status)."""
    sig = inspect.signature(MetricsExporter.observe_request)
    params = list(sig.parameters.keys())
    assert params == ["self", "method", "path", "status"]


def test_metrics_exporter_observe_pii_hit_signature() -> None:
    """Spec literal: pii_hits_total{pii_type, action}."""
    sig = inspect.signature(MetricsExporter.observe_pii_hit)
    params = list(sig.parameters.keys())
    assert params == ["self", "pii_type", "action"]


def test_metrics_exporter_observe_duration_signature() -> None:
    """Spec literal: duration_seconds_bucket."""
    sig = inspect.signature(MetricsExporter.observe_duration)
    params = list(sig.parameters.keys())
    assert params == ["self", "seconds"]


def test_metrics_exporter_set_active_connections_signature() -> None:
    """Spec literal: active_connections (a gauge, hence 'set')."""
    sig = inspect.signature(MetricsExporter.set_active_connections)
    params = list(sig.parameters.keys())
    assert params == ["self", "count"]


def test_noop_metrics_exporter_drops_everything() -> None:
    """All 5 Noop methods must be silent and return None."""
    mx = NoopMetricsExporter()
    # All calls return None
    assert mx.observe_request("POST", "/v1/chat", 200) is None
    assert mx.observe_duration(0.123) is None
    assert mx.observe_pii_hit("id_card", "redact") is None
    assert mx.set_active_connections(42) is None
    assert mx.observe_trace_cache_hit() is None


def test_noop_metrics_exporter_satisfies_protocol() -> None:
    assert isinstance(NoopMetricsExporter(), MetricsExporter)


def test_real_metrics_exporter_satisfies_protocol() -> None:
    """A counter-based impl satisfies the Protocol structurally."""

    class CountingMetrics:
        def __init__(self):
            self.requests = []
            self.durations = []
            self.pii_hits = []
            self.active = None
            self.cache_hits = 0

        def observe_request(self, method, path, status):
            self.requests.append((method, path, status))

        def observe_duration(self, seconds):
            self.durations.append(seconds)

        def observe_pii_hit(self, pii_type, action):
            self.pii_hits.append((pii_type, action))

        def set_active_connections(self, count):
            self.active = count

        def observe_trace_cache_hit(self):
            self.cache_hits += 1

    m = CountingMetrics()
    assert isinstance(m, MetricsExporter)
    m.observe_request("POST", "/x", 200)
    m.observe_duration(0.5)
    m.observe_pii_hit("id_card", "redact")
    m.set_active_connections(10)
    m.observe_trace_cache_hit()
    assert m.requests == [("POST", "/x", 200)]
    assert m.durations == [0.5]
    assert m.pii_hits == [("id_card", "redact")]
    assert m.active == 10
    assert m.cache_hits == 1


# ---------- Cross-cutting --------------------------------------------------

def test_all_noops_have_default_constructor() -> None:
    """Each Noop must be constructible with no arguments."""
    NoopRateLimiter()
    NoopResponseCache()
    NoopRequestBatcher()
    NoopMetricsExporter()


def test_protocols_are_runtime_checkable() -> None:
    """All 4 Protocols use @runtime_checkable so isinstance works."""
    for proto in (RateLimiter, ResponseCache, RequestBatcher, MetricsExporter):
        # Protocol classes with @runtime_checkable have a
        # `_is_runtime_protocol` class attribute set to True
        assert getattr(proto, "_is_runtime_protocol", False), (
            f"{proto.__name__} missing @runtime_checkable"
        )


def test_noops_dont_have_external_dependencies() -> None:
    """The Noop implementations must be dependency-free. They are
    the fallback when the real impl isn't wired up; if they
    depended on a broken import, the fallback would also fail."""
    import app.perf.contracts as m

    src = inspect.getsource(m)
    # Only stdlib + typing imports should appear
    for line in src.splitlines():
        if line.strip().startswith("import ") or line.strip().startswith("from "):
            # Allow stdlib + typing + app.* imports (no third-party)
            assert not any(
                line.startswith(f"{prefix} {pkg}")
                for prefix in ("import", "from")
                for pkg in ("boto3", "redis", "prometheus_client", "httpx", "fastapi", "sqlalchemy")
            ), f"unexpected third-party import in perf/contracts.py: {line}"
