"""Unit tests for the audit hash + outbox writer.

Two things under test:

* ``prompt_hash`` is stable + order-sensitive (a chat with two
  messages in different order produces a different hash).
* ``AuditOutbox._write_with_retry`` retries on DB failure and
  gives up after 3 attempts without raising. The chat handler
  must not be crashed by a stuck audit write.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.audit.hash import prompt_hash
from app.audit.writer import AuditOutbox
from app.models.audit import AuditLog


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestPromptHash(unittest.TestCase):
    """prompt_hash() stability + order-sensitivity."""

    def test_same_input_same_hash(self):
        msgs = [{"role": "user", "content": "hello"}]
        h1 = prompt_hash(msgs)
        h2 = prompt_hash(msgs)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)  # SHA-256 hex

    def test_different_content_different_hash(self):
        h1 = prompt_hash([{"role": "user", "content": "hello"}])
        h2 = prompt_hash([{"role": "user", "content": "world"}])
        self.assertNotEqual(h1, h2)

    def test_order_matters(self):
        h1 = prompt_hash(
            [
                {"role": "user", "content": "a"},
                {"role": "assistant", "content": "b"},
            ]
        )
        h2 = prompt_hash(
            [
                {"role": "assistant", "content": "b"},
                {"role": "user", "content": "a"},
            ]
        )
        self.assertNotEqual(h1, h2)

    def test_hex_lowercase(self):
        h = prompt_hash([{"role": "user", "content": "x"}])
        # Lower-case hex only (CHAR(64) column is case-sensitive).
        self.assertEqual(h, h.lower())
        self.assertTrue(all(c in "0123456789abcdef" for c in h))

    def test_empty_list(self):
        # Edge: empty list should still hash (no crash).
        h = prompt_hash([])
        self.assertEqual(len(h), 64)


class TestAuditOutboxRetry(unittest.TestCase):
    """AuditOutbox._write_with_retry() behaviour."""

    def _make_record(self) -> AuditLog:
        return AuditLog(
            trace_id="t-12345678",
            user_id="svc-test",
            model="qwen-max",
            model_kind="public",
            prompt_hash="0" * 64,
            latency_ms=10,
        )

    def test_success_first_try(self):
        rec = self._make_record()
        outbox = AuditOutbox()
        # Patch get_session to succeed immediately
        fake_session = AsyncMock()
        fake_session.__aenter__ = AsyncMock(return_value=fake_session)
        fake_session.__aexit__ = AsyncMock(return_value=None)
        fake_session.add = AsyncMock()
        fake_session.commit = AsyncMock()
        with patch("app.audit.writer.get_session", return_value=fake_session):
            _run(outbox._write_with_retry(rec))
        # Only one commit on the first-try success
        self.assertEqual(fake_session.commit.await_count, 1)

    def test_retries_then_succeeds(self):
        rec = self._make_record()
        outbox = AuditOutbox()

        attempt_counter = {"n": 0}

        def make_session():
            attempt_counter["n"] += 1
            session = AsyncMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=None)
            session.add = AsyncMock()
            if attempt_counter["n"] < 3:
                # First two attempts: commit raises
                session.commit = AsyncMock(side_effect=RuntimeError("db transient"))
            else:
                # Third attempt: commit succeeds
                session.commit = AsyncMock()
            return session

        # ``get_session`` is called as an async context manager factory;
        # patch it to return a fresh session per call.
        with patch("app.audit.writer.get_session", side_effect=make_session):
            _run(outbox._write_with_retry(rec))
        # 3 calls to get_session: 2 failed + 1 succeeded
        self.assertEqual(attempt_counter["n"], 3)

    def test_gives_up_after_3_failures(self):
        rec = self._make_record()
        outbox = AuditOutbox()

        attempt_counter = {"n": 0}

        def make_session():
            attempt_counter["n"] += 1
            session = AsyncMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=None)
            session.add = AsyncMock()
            session.commit = AsyncMock(side_effect=RuntimeError("db down"))
            return session

        # The function should not raise even after 3 failures
        with patch("app.audit.writer.get_session", side_effect=make_session):
            _run(outbox._write_with_retry(rec))
        # Exactly 3 attempts
        self.assertEqual(attempt_counter["n"], 3)

    def test_enqueue_drops_on_full_queue(self):
        """Enqueueing past the queue size drops the record silently
        (logs an error but does not raise)."""
        outbox = AuditOutbox()
        # Shrink the queue for the test
        outbox._queue = asyncio.Queue(maxsize=2)
        outbox._queue.put_nowait(self._make_record())
        outbox._queue.put_nowait(self._make_record())
        # Third enqueue: should drop without raising
        outbox.enqueue(self._make_record())
        # Queue still has 2 records
        self.assertEqual(outbox._queue.qsize(), 2)

    def test_stop_handles_timeout_gracefully(self):
        """stop() catches asyncio.TimeoutError and logs a warning,
        then sets _task to None (covers writer.py:60-61)."""
        outbox = AuditOutbox()

        class _NeverDone:
            @staticmethod
            def done():
                return False

        outbox._task = _NeverDone()

        # Replace asyncio.wait_for to simulate timeout
        async def _fake_wait_for(awaitable, timeout):
            raise asyncio.TimeoutError()

        with patch.object(asyncio, "wait_for", _fake_wait_for):
            _run(outbox.stop())
        self.assertIsNone(outbox._task)


if __name__ == "__main__":
    unittest.main()
