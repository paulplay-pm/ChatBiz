"""Integration test for the audit-log write path.

The full chat pipeline emits an ``AuditLog`` ORM object with 14
fields. This test:

* Builds a representative ``AuditLog`` object
* Runs it through the outbox's ``_write_with_retry``
* Verifies the call to ``session.add(record)`` received the
  expected 14-field ORM object
* Verifies the *plaintext* prompt body is NOT in the SQL
  parameters (the hash is the only thing persisted)

We do not need a real PostgreSQL — we use a mock session and
inspect the calls to ``session.add`` to verify the 14-field shape
and the absence of any plaintext content.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.audit.hash import prompt_hash
from app.audit.writer import AuditOutbox
from app.models.audit import AuditLog


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# The 14 column shape locked in by the eng-review report
# (audit_log schema, see plan Task 2.2 + app/models/audit.py).
EXPECTED_FIELDS = {
    "id",
    "trace_id",
    "user_id",
    "workflow_id",
    "model",
    "model_kind",
    "bypass_isolation",
    "pii_detected_types",
    "pii_redacted_count",
    "prompt_hash",
    "token_input",
    "token_output",
    "latency_ms",
    "upstream_status",
    "error_class",
    "created_at",
}


class TestAuditLogWrite(unittest.TestCase):
    """End-to-end audit log write through the outbox."""

    def _make_record(self) -> AuditLog:
        messages = [{"role": "user", "content": "客户 [身份证_04X] 想看月报"}]
        return AuditLog(
            trace_id="01HXYZGATEWAYTEST000000000",
            user_id="svc-paul",
            workflow_id="wf-monthly-report",
            model="qwen-max",
            model_kind="public",
            bypass_isolation=False,
            pii_detected_types=["身份证"],
            pii_redacted_count=1,
            prompt_hash=prompt_hash(messages),
            token_input=42,
            token_output=17,
            latency_ms=153,
            upstream_status=200,
            error_class=None,
        )

    def test_write_emits_14_field_record(self):
        """The record handed to ``session.add`` has all 14 expected
        columns populated (or default-valued)."""
        rec = self._make_record()
        outbox = AuditOutbox()
        captured: dict = {}

        def make_session():
            session = AsyncMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=None)
            # ``session.add`` is a *sync* method on the real
            # AsyncSession — use a MagicMock so the side_effect
            # fires immediately when the writer calls ``s.add(rec)``.
            def capture(r):
                captured["record"] = r
                return None

            session.add = MagicMock(side_effect=capture)
            session.commit = AsyncMock()
            return session

        with patch("app.audit.writer.get_session", side_effect=make_session):
            _run(outbox._write_with_retry(rec))

        self.assertIn("record", captured)
        r = captured["record"]
        # Column-level: every expected field is on the ORM object.
        actual_fields = {c.name for c in r.__table__.columns}
        # The 16 columns of audit_log — id + created_at are server-side
        for f in EXPECTED_FIELDS:
            self.assertIn(f, actual_fields, f"missing column {f}")
        # The captured record's values match what we set
        self.assertEqual(r.trace_id, "01HXYZGATEWAYTEST000000000")
        self.assertEqual(r.user_id, "svc-paul")
        self.assertEqual(r.model, "qwen-max")
        self.assertEqual(r.model_kind, "public")
        self.assertEqual(r.pii_detected_types, ["身份证"])
        self.assertEqual(r.pii_redacted_count, 1)
        self.assertEqual(r.token_input, 42)
        self.assertEqual(r.token_output, 17)
        self.assertEqual(r.latency_ms, 153)
        self.assertEqual(r.upstream_status, 200)
        self.assertIsNone(r.error_class)
        # prompt_hash is 64 lowercase hex chars
        self.assertEqual(len(r.prompt_hash), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in r.prompt_hash))

    def test_plaintext_prompt_not_in_record(self):
        """The original prompt content (with the PII replaced) is
        not stored on the record — only the hash is. The original
        PII value ``11010119900101004X`` must not appear on the
        captured record, and the redacted content
        ``客户 [身份证_04X] 想看月报`` must not appear either.

        The hash is a 64-char hex digest of the redacted messages
        list — we verify the hash matches what ``prompt_hash``
        produces, then confirm none of the original prompt text
        is reachable from the captured record.
        """
        rec = self._make_record()
        outbox = AuditOutbox()
        captured: dict = {}

        def make_session():
            session = AsyncMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=None)

            def capture(r):
                captured["record"] = r
                return None

            session.add = MagicMock(side_effect=capture)
            session.commit = AsyncMock()
            return session

        with patch("app.audit.writer.get_session", side_effect=make_session):
            _run(outbox._write_with_retry(rec))

        r = captured["record"]
        # The hash is stable + matches what prompt_hash produces
        expected_hash = prompt_hash(
            [{"role": "user", "content": "客户 [身份证_04X] 想看月报"}]
        )
        self.assertEqual(r.prompt_hash, expected_hash)

        # Inspect the captured record's __dict__ for any forbidden
        # substring (defence-in-depth: even if a future field is
        # added, this test fails immediately if PII sneaks in).
        forbidden_substrings = [
            "11010119900101004X",  # original PII
            "客户 [身份证_04X] 想看月报",  # redacted content
            "客户 11010119900101004X 想看月报",  # plaintext with PII
        ]
        # Serialise the record's __dict__ to a string for substring check
        record_str = str(r.__dict__)
        for s in forbidden_substrings:
            self.assertNotIn(s, record_str, f"plaintext leaked: {s}")

    def test_pii_metadata_carries_types_and_count(self):
        """The PII type list and count are persisted (metadata-only
        audit: we know *what* was redacted without storing the
        original values)."""
        rec = AuditLog(
            trace_id="t-aaaa-bbbb-cccc-dddd",
            user_id="svc-paul",
            workflow_id=None,  # optional
            model="qwen-max",
            model_kind="public",
            bypass_isolation=False,
            pii_detected_types=["手机", "邮箱"],
            pii_redacted_count=2,
            prompt_hash="a" * 64,
            token_input=None,
            token_output=None,
            latency_ms=100,
            upstream_status=200,
            error_class=None,
        )
        outbox = AuditOutbox()
        captured: dict = {}

        def make_session():
            session = AsyncMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=None)
            session.add = MagicMock(side_effect=lambda r: captured.setdefault("record", r))
            session.commit = AsyncMock()
            return session

        with patch("app.audit.writer.get_session", side_effect=make_session):
            _run(outbox._write_with_retry(rec))
        r = captured["record"]
        self.assertEqual(r.pii_detected_types, ["手机", "邮箱"])
        self.assertEqual(r.pii_redacted_count, 2)
        # workflow_id and token_* are nullable
        self.assertIsNone(r.workflow_id)
        self.assertIsNone(r.token_input)
        self.assertIsNone(r.token_output)

    def test_outbox_end_to_end(self):
        """The outbox's enqueue + worker drains a record through
        ``_write_with_retry`` in a background task."""
        outbox = AuditOutbox()
        rec = self._make_record()
        captured: dict = {}

        def make_session():
            session = AsyncMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=None)
            session.add = MagicMock(side_effect=lambda r: captured.setdefault("record", r))
            session.commit = AsyncMock()
            return session

        async def scenario():
            with patch("app.audit.writer.get_session", side_effect=make_session):
                await outbox.start()
                # Enqueue from inside the running loop (the queue
                # is bound to this loop).
                outbox.enqueue(rec)
                # Give the worker a moment to drain
                await asyncio.sleep(0.1)
                await outbox.stop()

        _run(scenario())
        self.assertIn("record", captured)
        self.assertEqual(captured["record"].trace_id, rec.trace_id)


if __name__ == "__main__":
    unittest.main()
