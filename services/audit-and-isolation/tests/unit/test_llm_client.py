"""Unit tests for ``app.llm.client.call_upstream``.

Covers the retry behaviour the plan calls out:

* 5xx on the first attempt + 200 on the second → returns 200.
* timeout on the first attempt + timeout on the second → raises
  ``httpx.TimeoutException`` (the gateway's Phase 9 layer maps
  this to ``UpstreamTimeout``).
* 4xx is *not* retried.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.llm.client import call_upstream, reset_client_for_tests


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_response(status_code: int, json_body: dict | None = None) -> httpx.Response:
    """Build an ``httpx.Response`` for testing without a real network."""
    return httpx.Response(
        status_code=status_code,
        json=json_body or {"ok": True},
        request=httpx.Request("POST", "http://example.com/v1/chat/completions"),
    )


class TestCallUpstream(unittest.TestCase):
    """call_upstream() retry behaviour."""

    def setUp(self):
        reset_client_for_tests()

    def test_returns_first_2xx(self):
        ok = _mock_response(200, {"choices": []})
        client = AsyncMock()
        client.post = AsyncMock(return_value=ok)
        with patch("app.llm.client.get_client", return_value=client):
            resp = _run(call_upstream("http://x", "/v1", {}, {}))
        self.assertEqual(resp.status_code, 200)
        # Exactly one POST — no retry on success
        self.assertEqual(client.post.await_count, 1)

    def test_retries_on_5xx_then_succeeds(self):
        bad = _mock_response(503)
        ok = _mock_response(200, {"ok": True})
        client = AsyncMock()
        # First call returns 503, second returns 200
        client.post = AsyncMock(side_effect=[bad, ok])
        with patch("app.llm.client.get_client", return_value=client):
            resp = _run(call_upstream("http://x", "/v1", {}, {}))
        self.assertEqual(resp.status_code, 200)
        # Two POSTs — the retry happened
        self.assertEqual(client.post.await_count, 2)

    def test_no_retry_on_4xx(self):
        # 4xx is the caller's fault — don't retry
        bad = _mock_response(400, {"error": "bad request"})
        client = AsyncMock()
        client.post = AsyncMock(return_value=bad)
        with patch("app.llm.client.get_client", return_value=client):
            resp = _run(call_upstream("http://x", "/v1", {}, {}))
        self.assertEqual(resp.status_code, 400)
        # No retry on 4xx — only one POST
        self.assertEqual(client.post.await_count, 1)

    def test_timeout_retries_then_raises(self):
        client = AsyncMock()
        client.post = AsyncMock(side_effect=httpx.TimeoutException("upstream timeout"))
        with patch("app.llm.client.get_client", return_value=client):
            with self.assertRaises(httpx.TimeoutException):
                _run(call_upstream("http://x", "/v1", {}, {}))
        # Two attempts: first timeout, sleep 200 ms, second timeout
        self.assertEqual(client.post.await_count, 2)

    def test_5xx_5xx_returns_5xx(self):
        # Two 5xx → the second 5xx is returned (not retried further)
        bad1 = _mock_response(500)
        bad2 = _mock_response(502)
        client = AsyncMock()
        client.post = AsyncMock(side_effect=[bad1, bad2])
        with patch("app.llm.client.get_client", return_value=client):
            resp = _run(call_upstream("http://x", "/v1", {}, {}))
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(client.post.await_count, 2)

    def test_url_concatenation(self):
        # Verifies the path is appended to the base url, with no
        # double slash.
        ok = _mock_response(200)
        client = AsyncMock()
        client.post = AsyncMock(return_value=ok)
        with patch("app.llm.client.get_client", return_value=client):
            _run(call_upstream("http://example.com/", "/v1/chat/completions", {}, {}))
        call_args = client.post.call_args
        self.assertEqual(call_args.args[0], "http://example.com/v1/chat/completions")


if __name__ == "__main__":
    unittest.main()
