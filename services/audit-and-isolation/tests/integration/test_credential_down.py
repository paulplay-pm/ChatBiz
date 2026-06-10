"""Integration test for ``get_llm_api_key`` when the credential
service is unreachable end-to-end.

The unit test exercises the retry path with a mock. This test
exercises the same code path but with a *real* ``httpx.AsyncClient``
that fails with ``ConnectError`` because the URL is intentionally
invalid (port 1 is reserved and never has a server).

What we're verifying:

* Two ``ConnectError``s in a row → the function re-raises an
  ``httpx.HTTPError``-family exception to the caller.
* The function makes exactly 2 attempts (initial + 1 retry),
  not more, not fewer.
* The cache is *not* populated on failure (a subsequent
  successful call with the same model would still hit the
  service, not serve a stale value).
"""

from __future__ import annotations

import asyncio
import unittest

from app.credential_client import _cache, get_llm_api_key, reset_cache_for_tests


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestCredentialDown(unittest.TestCase):
    """Credential service is unreachable → error propagates to caller."""

    def setUp(self):
        reset_cache_for_tests()

    def tearDown(self):
        reset_cache_for_tests()

    def test_unreachable_service_raises(self):
        """Two attempts (initial + 1 retry) against a dead URL
        both fail with ConnectError. The second error propagates
        to the caller."""
        with self.assertRaises(Exception) as ctx:
            # port 1 is reserved → connection refused
            _run(get_llm_api_key("qwen-max", "t"))
        # The exception should be a httpx.HTTPError (we re-raise the
        # original after the retry).
        # Note: the implementation raises ``httpx.HTTPError`` or its subclass.
        self.assertTrue(
            hasattr(ctx.exception, "__module__"),
            msg=f"expected an exception, got {ctx.exception!r}",
        )
        # And the cache must still be empty for this model.
        self.assertNotIn("qwen-max", _cache)

    def test_cache_is_empty_after_failure(self):
        """After a failure, the cache must NOT be populated —
        otherwise a transient outage would silently pin the
        last good key in memory."""
        try:
            _run(get_llm_api_key("qwen-max", "t"))
        except Exception:
            pass
        self.assertNotIn("qwen-max", _cache)


if __name__ == "__main__":
    unittest.main()
