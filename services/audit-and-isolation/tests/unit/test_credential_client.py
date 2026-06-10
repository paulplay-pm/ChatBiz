"""Unit tests for ``app.credential_client.get_llm_api_key``.

3 cases the plan calls out:

* **Cache hit** — two calls within the TTL produce only one
  HTTP request to the credential service.
* **Cache expiry** — after the TTL elapses, the next call
  re-fetches.
* **503 retry** — a 503 on the first attempt is retried once
  and the retry's 200 is returned; two 503s in a row raise
  :class:`CredentialServiceUnavailable`-style error.

The 5-minute TTL is overridden in the test by monkey-patching
``get_settings()`` to return a much shorter TTL so the cache
expiry test doesn't have to sleep.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock, patch

import httpx

from app.credential_client import get_llm_api_key, reset_cache_for_tests


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _PostRecorder:
    """Records every call to ``post``; replays a configured sequence of
    status codes / JSON bodies.

    Usage::

        rec = _PostRecorder([(200, {"api_key": "k1"}), (503, None)])
        # First call returns 200, second returns 503 (after the
        # 200 ms retry sleep).
    """

    def __init__(self, responses: list[tuple[int, dict | None]], raise_exc: Exception | None = None):
        self.responses = list(responses)
        self.raise_exc = raise_exc
        self.calls: list[tuple[str, dict]] = []

    def make_client(self):
        rec = self

        class _Client:
            async def post(inner_self, url, json=None):
                rec.calls.append((url, json))
                if rec.raise_exc is not None:
                    raise rec.raise_exc
                status, body = rec.responses.pop(0)
                resp = MagicMock()
                resp.status_code = status
                resp.json = MagicMock(return_value=body or {})
                return resp

        class _Ctx:
            async def __aenter__(self_inner):
                return _Client()

            async def __aexit__(self_inner, *exc):
                return None

        return _Ctx()


class TestGetLLMApiKey(unittest.TestCase):
    """The 3-case matrix from the plan."""

    def setUp(self):
        reset_cache_for_tests()
        # Use a short TTL so the cache-expiry test is fast.
        # We patch get_settings to return a tiny credential_cache_ttl_seconds.
        from app import credential_client as cc

        original_get_settings = cc.get_settings

        def _short_ttl_settings():
            s = original_get_settings()
            s.credential_cache_ttl_seconds = 1
            return s

        self._patcher = patch.object(cc, "get_settings", _short_ttl_settings)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        reset_cache_for_tests()

    def test_cache_hit_makes_only_one_http_call(self):
        rec = _PostRecorder([(200, {"api_key": "sk-test-1"})])
        with patch("app.credential_client.httpx.AsyncClient", new=lambda *a, **kw: rec.make_client()):
            k1 = _run(get_llm_api_key("qwen-max", "t"))
            k2 = _run(get_llm_api_key("qwen-max", "t"))
        self.assertEqual(k1, "sk-test-1")
        self.assertEqual(k2, "sk-test-1")
        # Only one HTTP call — second was a cache hit.
        self.assertEqual(len(rec.calls), 1)

    def test_cache_expiry_triggers_refetch(self):
        rec = _PostRecorder(
            [
                (200, {"api_key": "sk-test-1"}),
                (200, {"api_key": "sk-test-2"}),
            ]
        )
        with patch("app.credential_client.httpx.AsyncClient", new=lambda *a, **kw: rec.make_client()):
            k1 = _run(get_llm_api_key("qwen-max", "t"))
        # Wait for TTL (1s) to elapse, then refetch.
        import time

        time.sleep(1.2)
        with patch("app.credential_client.httpx.AsyncClient", new=lambda *a, **kw: rec.make_client()):
            k2 = _run(get_llm_api_key("qwen-max", "t"))
        self.assertEqual(k1, "sk-test-1")
        self.assertEqual(k2, "sk-test-2")
        # Two HTTP calls (one per TTL window).
        self.assertEqual(len(rec.calls), 2)

    def test_503_retries_once_and_succeeds(self):
        rec = _PostRecorder(
            [
                (503, None),  # first attempt: 503
                (200, {"api_key": "sk-retry"}),  # retry: 200
            ]
        )
        with patch("app.credential_client.httpx.AsyncClient", new=lambda *a, **kw: rec.make_client()):
            k = _run(get_llm_api_key("qwen-max", "t"))
        self.assertEqual(k, "sk-retry")
        self.assertEqual(len(rec.calls), 2)

    def test_503_twice_raises_runtimeerror(self):
        rec = _PostRecorder(
            [
                (503, None),
                (503, None),
            ]
        )
        with patch("app.credential_client.httpx.AsyncClient", new=lambda *a, **kw: rec.make_client()):
            with self.assertRaises(RuntimeError):
                _run(get_llm_api_key("qwen-max", "t"))
        self.assertEqual(len(rec.calls), 2)

    def test_network_error_retries_once(self):
        rec = _PostRecorder([], raise_exc=httpx.ConnectError("boom"))
        with patch("app.credential_client.httpx.AsyncClient", new=lambda *a, **kw: rec.make_client()):
            with self.assertRaises(httpx.HTTPError):
                _run(get_llm_api_key("qwen-max", "t"))


if __name__ == "__main__":
    unittest.main()
