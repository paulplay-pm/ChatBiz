"""Unit tests for ``app.llm.retry.RetryWithIdempotency``.

Covers the HA failover retry behaviour the gateway-egress P0 spec
locks in (D3):

* 503 HA_FAILOVER → retry up to 3 times within 5s
* ConnectionError → retry
* 5xx (non-503 HA_FAILOVER) → no retry (the upstream 1-retry path
  already handles generic 5xx; this decorator only fires on the
  specific failover signal)
* Idempotency-Key = SHA-256 of (user_id + body_hash + 5min bucket)
  and must be stable across the 3 attempts within the same bucket
* 3 consecutive HAFailoverError → raise HAFailoverExhausted
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import unittest
from unittest.mock import AsyncMock, patch

from app.llm.retry import (
    HAFailoverError,
    HAFailoverExhausted,
    RetryWithIdempotency,
    compute_idempotency_key,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _expected_key(user_id: str, body: dict, ts: float) -> str:
    body_hash = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    bucket = int(ts) // 300
    raw = f"{user_id}{body_hash}{bucket}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class TestComputeIdempotencyKey(unittest.TestCase):
    """compute_idempotency_key() is deterministic within a 5-min bucket."""

    def test_deterministic_within_bucket(self):
        body = {"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]}
        ts = 1_700_000_000.0
        k1 = compute_idempotency_key("user-1", body, ts)
        k2 = compute_idempotency_key("user-1", body, ts)
        self.assertEqual(k1, k2)

    def test_bucket_changes_after_5_min(self):
        body = {"model": "gpt-4"}
        ts_a = 1_700_000_000.0  # bucket 5666666
        ts_b = ts_a + 300  # exactly 5 min later → next bucket
        self.assertNotEqual(
            compute_idempotency_key("u", body, ts_a),
            compute_idempotency_key("u", body, ts_b),
        )

    def test_user_id_changes_key(self):
        body = {"x": 1}
        ts = 1_700_000_000.0
        self.assertNotEqual(
            compute_idempotency_key("user-a", body, ts),
            compute_idempotency_key("user-b", body, ts),
        )

    def test_body_changes_key(self):
        ts = 1_700_000_000.0
        self.assertNotEqual(
            compute_idempotency_key("u", {"a": 1}, ts),
            compute_idempotency_key("u", {"a": 2}, ts),
        )

    def test_matches_documented_formula(self):
        body = {"k": "v"}
        ts = 1_700_000_123.0
        self.assertEqual(
            compute_idempotency_key("u-1", body, ts),
            _expected_key("u-1", body, ts),
        )


class TestRetryWithIdempotency(unittest.TestCase):
    """The decorator's retry semantics on top of an async callable."""

    def test_succeeds_first_try_no_retry(self):
        calls = []

        @RetryWithIdempotency()
        async def func(user_id, body, *, idempotency_key):
            calls.append((user_id, body))
            return "ok"

        result = _run(func("u-1", {"x": 1}))
        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 1)

    def test_retries_on_ha_failover_then_succeeds(self):
        """First 2 calls raise HAFailoverError(503), third succeeds → called 3 times."""
        calls = []

        @RetryWithIdempotency(max_retries=3, window_seconds=5)
        async def func(user_id, body, *, idempotency_key):
            calls.append(body)
            if len(calls) < 3:
                raise HAFailoverError("503 HA_FAILOVER", status_code=503)
            return {"ok": True, "attempt": len(calls)}

        result = _run(func("u-1", {"x": 1}))
        self.assertEqual(result, {"ok": True, "attempt": 3})
        self.assertEqual(len(calls), 3)

    def test_three_failovers_raises_exhausted(self):
        """3 consecutive HAFailoverError → HAFailoverExhausted."""
        calls = []

        @RetryWithIdempotency(max_retries=3, window_seconds=5)
        async def func(user_id, body, *, idempotency_key):
            calls.append(body)
            raise HAFailoverError("503 HA_FAILOVER", status_code=503)

        with self.assertRaises(HAFailoverExhausted):
            _run(func("u-1", {"x": 1}))
        # 3 attempts total (initial + 2 retries) before exhaustion.
        self.assertEqual(len(calls), 3)

    def test_retries_on_connection_error(self):
        """ConnectionError is retried (treated like HA failover transport glitch)."""
        calls = []

        @RetryWithIdempotency(max_retries=3, window_seconds=5)
        async def func(user_id, body, *, idempotency_key):
            calls.append(body)
            if len(calls) < 2:
                raise ConnectionError("connection reset")
            return "recovered"

        result = _run(func("u-1", {"x": 1}))
        self.assertEqual(result, "recovered")
        self.assertEqual(len(calls), 2)

    def test_5xx_non_503_is_not_retried(self):
        """Non-503 5xx (e.g. 500/502) must NOT trigger the HA failover retry."""
        calls = []

        @RetryWithIdempotency(max_retries=3, window_seconds=5)
        async def func(user_id, body, *, idempotency_key):
            calls.append(body)
            raise HAFailoverError("500 upstream", status_code=500)

        with self.assertRaises(HAFailoverError):
            _run(func("u-1", {"x": 1}))
        # Exactly one attempt — no retry on non-503 5xx.
        self.assertEqual(len(calls), 1)

    def test_idempotency_key_stable_across_retries(self):
        """The Idempotency-Key passed in kwargs['idempotency_key'] must be
        identical across the 3 retry attempts (same 5-min bucket)."""
        seen_keys: list[str] = []

        @RetryWithIdempotency(max_retries=3, window_seconds=5)
        async def func(user_id, body, *, idempotency_key):
            seen_keys.append(idempotency_key)
            if len(seen_keys) < 3:
                raise HAFailoverError("503 HA_FAILOVER", status_code=503)
            return "ok"

        with patch("app.llm.retry.time.time", return_value=1_700_000_100.0):
            _run(func("u-1", {"x": 1}))

        self.assertEqual(len(seen_keys), 3)
        self.assertEqual(seen_keys[0], seen_keys[1])
        self.assertEqual(seen_keys[1], seen_keys[2])
        # And matches the documented formula.
        expected = _expected_key("u-1", {"x": 1}, 1_700_000_100.0)
        self.assertEqual(seen_keys[0], expected)

    def test_idempotency_key_changes_after_bucket_boundary(self):
        """When retries cross a 5-min bucket boundary, the key may differ —
        but within a single bucket it must be stable."""
        seen_keys: list[str] = []
        timestamps = [1_700_000_000.0, 1_700_000_000.0, 1_700_000_600.0]

        @RetryWithIdempotency(max_retries=3, window_seconds=5)
        async def func(user_id, body, *, idempotency_key):
            seen_keys.append(idempotency_key)
            if len(seen_keys) < 3:
                raise HAFailoverError("503 HA_FAILOVER", status_code=503)
            return "ok"

        with patch("app.llm.retry.time.time", side_effect=timestamps):
            _run(func("u-1", {"x": 1}))

        # First two retries in bucket 5666666, third in bucket 5666668.
        self.assertEqual(len(seen_keys), 3)
        self.assertEqual(seen_keys[0], seen_keys[1])
        self.assertNotEqual(seen_keys[0], seen_keys[2])

    def test_sleep_between_retries(self):
        """Failed attempts sleep with the configured window budget."""
        calls = []

        @RetryWithIdempotency(max_retries=3, window_seconds=5)
        async def func(user_id, body, *, idempotency_key):
            calls.append(body)
            raise HAFailoverError("503 HA_FAILOVER", status_code=503)

        with patch("app.llm.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with self.assertRaises(HAFailoverExhausted):
                _run(func("u-1", {"x": 1}))
        # 3 attempts → 2 sleeps in between.
        self.assertEqual(mock_sleep.await_count, 2)
        # Both sleeps within the 5s window budget.
        for call in mock_sleep.await_args_list:
            self.assertLessEqual(call.args[0], 5)

    def test_non_retryable_exception_propagates_immediately(self):
        """ValueError is not a failover signal — must raise on first attempt."""
        calls = []

        @RetryWithIdempotency(max_retries=3, window_seconds=5)
        async def func(user_id, body, *, idempotency_key):
            calls.append(body)
            raise ValueError("bad input")

        with self.assertRaises(ValueError):
            _run(func("u-1", {"x": 1}))
        self.assertEqual(len(calls), 1)

    def test_returns_value_unchanged(self):
        """The decorator must not transform the wrapped function's return value."""

        @RetryWithIdempotency()
        async def func(*, idempotency_key):
            return {"id": 42, "tags": ["a", "b"]}

        result = _run(func())
        self.assertEqual(result, {"id": 42, "tags": ["a", "b"]})


class TestRetryWrapsClient(unittest.TestCase):
    """Smoke: RetryWithIdempotency composes with the existing call_upstream
    without mutating its 5xx single-retry behaviour."""

    def test_import_and_wrap(self):
        # Just ensure the import path works and decorator is a callable
        # instance (no import-time error, no exception types collide).
        from app.llm.client import call_upstream  # noqa: F401

        decorated = RetryWithIdempotency(max_retries=3, window_seconds=5)(
            call_upstream
        )
        self.assertTrue(callable(decorated))


class TestRetryWithIdempotencyValidation(unittest.TestCase):
    """Constructor argument validation."""

    def test_max_retries_must_be_positive(self):
        with self.assertRaises(ValueError):
            RetryWithIdempotency(max_retries=0)

    def test_window_seconds_must_be_positive(self):
        with self.assertRaises(ValueError):
            RetryWithIdempotency(max_retries=3, window_seconds=0)

    def test_negative_window_seconds_rejected(self):
        with self.assertRaises(ValueError):
            RetryWithIdempotency(max_retries=3, window_seconds=-1)


if __name__ == "__main__":
    unittest.main()