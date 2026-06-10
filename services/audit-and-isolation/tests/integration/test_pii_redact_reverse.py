"""Integration tests for the PII redact + reverse round trip.

We use ``fakeredis.aioredis`` as a drop-in for the real
``redis.asyncio.Redis`` so the redactor/reverser code path runs
end-to-end without a live Redis server. The client modules use
``redis.asyncio.Redis`` directly (not a custom wrapper), so the
fakeredis mock is injected by monkey-patching
:func:`app.redis_client.get_redis` — the modules under test call
``get_redis()`` lazily on each request, so monkey-patching the
factory is sufficient.
"""

from __future__ import annotations

import asyncio
import unittest

import fakeredis.aioredis

from app import redis_client
from app.pii.redactor import redact
from app.pii.reverser import reverse


def _run(coro):
    """Tiny ``asyncio.run`` wrapper so each test stays a sync
    ``unittest`` method (the project has no pytest-asyncio
    installed). Each call gets a fresh event loop to avoid
    cross-test interference from prior awaits."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestRedactReverse(unittest.TestCase):
    """End-to-end redaction + reversal behaviour."""

    def setUp(self):
        # Replace the real Redis with a fakeredis instance for the
        # duration of this test. ``reset_pool_for_tests`` clears the
        # module-level pool so the next ``get_redis()`` returns a
        # client backed by our fakeredis.
        redis_client.reset_pool_for_tests()
        self._fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
        self._original_get_redis = redis_client.get_redis
        redis_client.get_redis = lambda: self._fake

    def tearDown(self):
        # Restore the real factory so other test modules aren't
        # affected by our fakeredis substitution.
        redis_client.get_redis = self._original_get_redis
        redis_client.reset_pool_for_tests()
        _run(self._fake.aclose())

    def test_redact_id_card(self):
        text = f"客户 {self._valid_id_card()} 已确认"
        redacted, mapping, types = _run(redact("trace-1", text))
        # Placeholder format is [身份证_<4 hex>]
        self.assertIn("[身份证_", redacted)
        # The map has exactly one entry
        self.assertEqual(len(mapping), 1)
        # And it round-trips: reverse restores the original
        restored = _run(reverse("trace-1", redacted))
        self.assertEqual(restored, text)
        # Type list contains "身份证"
        self.assertIn("身份证", types)

    def test_redact_then_reverse(self):
        text = f"手机 13800138000 邮箱 zhang@example.com"
        redacted, mapping, types = _run(redact("trace-2", text))
        # Both placeholders present
        self.assertIn("[手机_", redacted)
        self.assertIn("[邮箱_", redacted)
        # Reverse restores both
        restored = _run(reverse("trace-2", redacted))
        self.assertEqual(restored, text)
        # Two types detected
        self.assertEqual(set(types), {"手机", "邮箱"})

    def test_second_redact_reuses_map(self):
        """Two redact() calls on the same trace share the same map key.

        The first call's map is overwritten by the second call's
        map (both go to the same Redis key). The reverser can then
        reverse placeholders from *either* call as long as they
        were both written under the same key — but the *latest*
        map wins for any placeholder that was rewritten.
        """
        text1 = f"id {self._valid_id_card()}"
        text2 = "phone 13800138000"
        red1, map1, _ = _run(redact("trace-3", text1))
        red2, map2, _ = _run(redact("trace-3", text2))
        # Each redact produced a placeholder for its own PII
        self.assertEqual(len(map1), 1)
        self.assertEqual(len(map2), 1)
        # Reverse of text1 uses the *latest* map (which is map2,
        # since both writes go to the same key). map1's placeholder
        # is no longer in Redis, so reverse returns the redacted
        # text unchanged.
        restored1 = _run(reverse("trace-3", red1))
        self.assertEqual(restored1, red1)
        # But text2's placeholder is in the latest map and reverses
        restored2 = _run(reverse("trace-3", red2))
        self.assertEqual(restored2, text2)

    def test_cross_trace_isolation(self):
        """A map written under trace-A is invisible to trace-B's
        reverse call."""
        text = "phone 13800138000"
        red_a, _, _ = _run(redact("trace-A", text))
        # trace-B has no map → reverse returns text unchanged
        restored_b = _run(reverse("trace-B", red_a))
        self.assertEqual(restored_b, red_a)
        # trace-A reverses correctly
        restored_a = _run(reverse("trace-A", red_a))
        self.assertEqual(restored_a, text)

    def test_no_pii_no_map(self):
        """A text with no PII should produce an empty map and the
        same text in, same text out."""
        text = "hello world, nothing to see here"
        red, mapping, types = _run(redact("trace-4", text))
        self.assertEqual(red, text)
        self.assertEqual(mapping, {})
        self.assertEqual(types, [])
        # Reverse of pure text is also no-op (no '[' in text)
        restored = _run(reverse("trace-4", red))
        self.assertEqual(restored, text)

    def test_reverse_no_bracket_short_circuits(self):
        """Plain text with no '[' skips the Redis lookup entirely."""
        # We never wrote the trace-5 map; this should not raise
        # even though Redis is empty.
        restored = _run(reverse("trace-5", "plain response from LLM"))
        self.assertEqual(restored, "plain response from LLM")

    def test_reverse_fail_open_on_redis_error(self):
        """If Redis raises on read, reverser returns the input unchanged
        (Fail-Open). We simulate by giving reverser a broken client."""
        # Build a stand-in redis that raises on get()
        class BrokenRedis:
            async def get(self, key):
                raise RuntimeError("simulated redis outage")

        original_get_redis = redis_client.get_redis
        redis_client.get_redis = lambda: BrokenRedis()
        try:
            restored = _run(reverse("trace-broken", "text [身份证_xx99] here"))
            self.assertEqual(restored, "text [身份证_xx99] here")
        finally:
            redis_client.get_redis = original_get_redis

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _valid_id_card() -> str:
        """A precomputed 18-char ID whose GB 11643-1999 mod-11 check
        digit validates. See ``tests/unit/test_pii_rules.py`` for
        the same fixture."""
        return "11010119900101004X"


if __name__ == "__main__":
    unittest.main()
