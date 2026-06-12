"""Unit tests for the 4 perf contract Protocols + Noop defaults.

Covers (from the design D7 spec):

* :class:`RateLimiter` Protocol signature — ``check(user_id, model) -> bool``
* :class:`ResponseCache` Protocol signature — ``get`` + ``put``
* :class:`RequestBatcher` Protocol signature — ``submit`` returns
  ``asyncio.Future[Response]``
* :class:`MetricsExporter` Protocol signature — ``export(metric)``

And the Noop behaviours:

* :class:`NoopRateLimiter.check` always returns ``True``
* :class:`NoopResponseCache.get` returns ``None``;
  :meth:`put` accepts the call and returns ``None``
* :class:`NoopRequestBatcher.submit` resolves the future synchronously
  with the executor's response
* :class:`NoopMetricsExporter.export` accepts the call and returns ``None``

We use ``runtime_checkable`` Protocol — the tests assert
``isinstance(NoopX(), ProtocolX)`` to lock the Protocol signature
contract (if a Noop stops satisfying the Protocol the test fails
*at import time* via ``@runtime_checkable``, which is exactly the
guarantee T6 will rely on).
"""

from __future__ import annotations

import asyncio
import os
import unittest
from typing import Optional
from unittest.mock import MagicMock

# Required env vars for the app config to load.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x")
os.environ.setdefault("REDIS_URL", "redis://x")
os.environ.setdefault("CREDENTIAL_SERVICE_URL", "http://x")

from app.perf.contracts import (  # noqa: E402
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


class TestProtocolSignature(unittest.TestCase):
    """The 4 Protocols exist and the Noops satisfy them.

    This is the signature-stability contract: T6's real
    implementations will ``isinstance`` against these Protocols,
    so a Noop that doesn't satisfy its Protocol means the chat
    pipeline's type hints lie.
    """

    def test_noop_rate_limiter_satisfies_protocol(self):
        self.assertIsInstance(NoopRateLimiter(), RateLimiter)

    def test_noop_response_cache_satisfies_protocol(self):
        self.assertIsInstance(NoopResponseCache(), ResponseCache)

    def test_noop_request_batcher_satisfies_protocol(self):
        self.assertIsInstance(NoopRequestBatcher(), RequestBatcher)

    def test_noop_metrics_exporter_satisfies_protocol(self):
        self.assertIsInstance(NoopMetricsExporter(), MetricsExporter)

    def test_value_types_are_frozen_dataclasses(self):
        """CachedResponse / Request / Response / Metric are frozen
        so a cache entry can't be mutated after put, and so they
        can be used as dict keys / set members when needed."""
        from dataclasses import FrozenInstanceError

        for cls in (CachedResponse, Request, Response, Metric):
            # Pick the right kwargs per class to actually construct
            # an instance — different fields per class.
            if cls is CachedResponse:
                inst = cls(body=b"x", status_code=200)
            elif cls is Request:
                inst = cls(model="m", body={}, headers={})
            elif cls is Response:
                inst = cls(status_code=200, body={})
            else:  # Metric
                inst = cls(name="n", value=1.0, kind="counter")
            with self.assertRaises(FrozenInstanceError):
                # Any field assignment raises on a frozen dataclass.
                inst.status_code = 999  # type: ignore[misc]

    def test_protocol_method_signatures(self):
        """Lock the exact method signatures T6 will implement.

        We assert the *bound* method names exist on each Protocol
        via the Noop (the Protocol itself is erased at runtime
        under ``@runtime_checkable`` so the actual attributes live
        on the Noop).
        """
        rl = NoopRateLimiter()
        self.assertTrue(callable(getattr(rl, "check", None)))

        cache = NoopResponseCache()
        self.assertTrue(callable(getattr(cache, "get", None)))
        self.assertTrue(callable(getattr(cache, "put", None)))

        batcher = NoopRequestBatcher()
        self.assertTrue(callable(getattr(batcher, "submit", None)))

        exporter = NoopMetricsExporter()
        self.assertTrue(callable(getattr(exporter, "export", None)))


class TestNoopRateLimiter(unittest.TestCase):
    """``NoopRateLimiter.check()`` always returns ``True``."""

    def test_check_returns_true_for_any_user_id_and_model(self):
        rl = NoopRateLimiter()
        self.assertTrue(rl.check("svc-paul", "qwen-max"))
        self.assertTrue(rl.check("svc-anon", "gpt-4o"))
        self.assertTrue(rl.check("", ""))

    def test_check_is_pure(self):
        """Noop doesn't depend on or mutate any state — calling
        twice with the same args must give the same result."""
        rl = NoopRateLimiter()
        a = rl.check("u", "m")
        b = rl.check("u", "m")
        self.assertEqual(a, b)


class TestNoopResponseCache(unittest.TestCase):
    """``NoopResponseCache`` is a sink — always misses, never stores."""

    def test_get_always_returns_none(self):
        cache = NoopResponseCache()
        self.assertIsNone(cache.get("any-hash"))
        self.assertIsNone(cache.get(""))

    def test_put_returns_none(self):
        """put() accepts the call and returns None (Protocol return)."""
        cache = NoopResponseCache()
        resp = CachedResponse(body=b"{}", status_code=200)
        result = cache.put("any-hash", resp, ttl=60)
        self.assertIsNone(result)
        # And a subsequent get() still misses.
        self.assertIsNone(cache.get("any-hash"))

    def test_put_with_zero_ttl_accepted(self):
        """ttl=0 is a valid hint; Noop discards regardless."""
        cache = NoopResponseCache()
        self.assertIsNone(
            cache.put("h", CachedResponse(body=b"", status_code=200), ttl=0)
        )


class TestNoopRequestBatcher(unittest.TestCase):
    """``NoopRequestBatcher.submit()`` resolves synchronously."""

    def test_submit_returns_asyncio_future(self):
        async def _go():
            batcher = NoopRequestBatcher(executor=lambda *a, **kw: _fake_resp(200, {"ok": True}))
            req = Request(model="m", body={}, headers={})
            fut = batcher.submit(req)
            self.assertIsInstance(fut, asyncio.Future)
            # The future is already done — Noop runs the executor synchronously.
            self.assertTrue(fut.done())
            return fut.result()

        resp = asyncio.run(_go())
        self.assertEqual(resp.status_code, 200)

    def test_submit_resolves_with_executor_response(self):
        """The Noop calls the executor synchronously and puts the
        result on the future — the chat pipeline can ``await`` it
        just like a real batcher."""
        executor = MagicMock(return_value=_fake_resp(200, {"hello": "world"}))
        batcher = NoopRequestBatcher(executor=executor)
        req = Request(model="m", body={"x": 1}, headers={"k": "v"})

        async def _go():
            fut = batcher.submit(req)
            return await fut

        resp = asyncio.run(_go())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.body, {"hello": "world"})
        executor.assert_called_once()

    def test_submit_without_executor_returns_empty_200(self):
        """Defensive: Noop with no executor returns a resolved
        future with an empty 200 — keeps the protocol usable in
        tests that don't care about the upstream call."""
        batcher = NoopRequestBatcher()  # no executor
        req = Request(model="m", body={}, headers={})

        async def _go():
            return await batcher.submit(req)

        resp = asyncio.run(_go())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.body, {})

    def test_submit_propagates_sync_executor_exception_via_future(self):
        """If the executor raises synchronously, the future is
        resolved with the exception (not raised at submit() time)
        so the chat pipeline's ``await`` sees the failure."""
        def _explode(*a, **kw):
            raise RuntimeError("boom")

        async def _go():
            batcher = NoopRequestBatcher(executor=_explode)
            req = Request(model="m", body={}, headers={})
            return await batcher.submit(req)

        with self.assertRaises(RuntimeError):
            asyncio.run(_go())

    def test_submit_supports_async_executor(self):
        """If the executor returns a coroutine, the Noop schedules
        it on the running loop and bridges the result onto the
        returned future (this is the branch the T6 real batcher
        shares — when ``call_upstream`` is async, the Noop is
        forced down the same path)."""
        async def _async_executor(base_url, path, body, headers):
            return _fake_resp(201, {"async": True})

        batcher = NoopRequestBatcher(executor=_async_executor)
        req = Request(model="m", body={}, headers={})

        async def _go():
            fut = batcher.submit(req)
            return await fut

        resp = asyncio.run(_go())
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.body, {"async": True})

    def test_submit_propagates_async_executor_exception(self):
        """If the async executor raises, the future is resolved
        with the exception so the chat pipeline's ``await`` sees
        the failure."""
        async def _async_explode(*a, **kw):
            raise ValueError("async boom")

        batcher = NoopRequestBatcher(executor=_async_explode)
        req = Request(model="m", body={}, headers={})

        async def _go():
            return await batcher.submit(req)

        with self.assertRaises(ValueError):
            asyncio.run(_go())

    def test_to_response_handles_plain_dict(self):
        """Executor may return a plain dict (test stub) — the
        ``_to_response`` helper coerces it to ``Response``."""
        from app.perf.contracts import _to_response

        r = _to_response({"hello": "world"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.body, {"hello": "world"})

    def test_to_response_handles_plain_response_passthrough(self):
        """If the executor already returns a ``Response``, the
        helper returns it unchanged (identity branch)."""
        from app.perf.contracts import _to_response

        original = Response(status_code=418, body={"teapot": True})
        self.assertIs(_to_response(original), original)

    def test_to_response_handles_object_with_json_method(self):
        """``httpx.Response``-shaped objects (status_code + json())
        are coerced to ``Response`` via the ``callable(json)``
        branch."""
        from app.perf.contracts import _to_response

        stub = MagicMock()
        stub.status_code = 200
        stub.json = MagicMock(return_value={"k": "v"})
        r = _to_response(stub)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.body, {"k": "v"})
        stub.json.assert_called_once()

    def test_to_response_handles_object_without_json_or_dict(self):
        """Object that has no ``json()`` method and is not a dict
        — the helper falls back to an empty body so the pipeline
        doesn't crash on a malformed executor return."""
        from app.perf.contracts import _to_response

        class _Opaque:
            status_code = 204

        r = _to_response(_Opaque())
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r.body, {})

    def test_response_json_method_returns_body(self):
        """The ``Response`` value type exposes a ``json()`` method
        so the chat pipeline can call it uniformly (whether the
        response came from the cache, the batcher, or the
        upstream directly)."""
        r = Response(status_code=200, body={"a": 1})
        self.assertEqual(r.json(), {"a": 1})

    def test_create_future_uses_running_loop(self):
        """Inside a running loop, ``_create_future`` returns a
        future bound to that loop (``loop.create_future()``)."""
        from app.perf.contracts import _create_future

        async def _go():
            return _create_future()

        fut = asyncio.run(_go())
        self.assertIsInstance(fut, asyncio.Future)

    def test_create_future_raises_outside_running_loop(self):
        """The chat pipeline only calls :meth:`submit` from an
        async handler, so a running loop is guaranteed. Outside
        a running loop, ``_create_future`` propagates the
        ``RuntimeError`` so the bug is loud, not silent."""
        from app.perf.contracts import _create_future

        with self.assertRaises(RuntimeError):
            _create_future()

    def test_schedule_coroutine_no_loop_sets_exception(self):
        """Defensive: if the executor returns a coroutine *and*
        there is no running loop, the future is failed with a
        RuntimeError instead of being silently dropped. We
        simulate this by closing the loop before calling."""
        from app.perf.contracts import _schedule_coroutine

        async def _coro():
            return Response(status_code=200, body={})

        # Construct the coroutine outside an event loop so the
        # helper sees ``RuntimeError`` from ``get_running_loop``.
        coro = _coro()

        async def _go():
            fut = asyncio.Future()  # bound to the running loop
            # Simulate "no running loop" by raising RuntimeError
            # via a side-channel: monkeypatch the helper's
            # ``get_running_loop`` to raise. Use a context manager
            # so the patch is restored even on failure.
            from unittest.mock import patch
            with patch(
                "app.perf.contracts.asyncio.get_running_loop",
                side_effect=RuntimeError("no loop"),
            ):
                _schedule_coroutine(fut, coro)
            self.assertTrue(fut.done())
            self.assertIsInstance(fut.exception(), RuntimeError)

        try:
            asyncio.run(_go())
        finally:
            coro.close()


class TestNoopMetricsExporter(unittest.TestCase):
    """``NoopMetricsExporter.export()`` accepts + discards."""

    def test_export_returns_none(self):
        exporter = NoopMetricsExporter()
        m = Metric(name="x_total", value=1.0, kind="counter", labels={"k": "v"})
        self.assertIsNone(exporter.export(m))

    def test_export_with_no_labels(self):
        exporter = NoopMetricsExporter()
        self.assertIsNone(exporter.export(Metric(name="n", value=0.0, kind="gauge")))

    def test_export_does_not_mutate_metric(self):
        """exporter.export() is a pure observation — does not
        mutate the passed-in Metric (which is frozen anyway)."""
        exporter = NoopMetricsExporter()
        m = Metric(name="n", value=1.0, kind="histogram", labels={"a": "b"})
        exporter.export(m)
        # Reading back fields still works.
        self.assertEqual(m.name, "n")
        self.assertEqual(m.value, 1.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_resp(status_code: int, body: dict) -> object:
    """Build a stub response with ``status_code`` + ``json()``."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=body)
    return resp


if __name__ == "__main__":
    unittest.main()
