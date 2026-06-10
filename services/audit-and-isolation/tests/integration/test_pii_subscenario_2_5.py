"""Critical-path e2e 2.5 — PII Fail-Open (detector 抛异常 → 不阻断).

The eng-review report's "PII Fail-Open" lock-in (finding #1):
if the PII detector crashes (e.g. a regex engine bug, a Redis
write failure that doesn't raise but returns a partial map,
an unexpected exception in the validator), the gateway MUST
pass the original body through to the upstream LLM
unredacted — *and* increment the
``pii_detector_fail_open_total`` counter so the on-call sees
the regression.

This is the conservative-Fail-Open direction: we prefer
disclosing the user's PII to a third-party LLM provider (a
recoverable privacy incident) over either (a) crashing the
chat request or (b) refusing to serve the user.

Test shape:

* Monkey-patch the redactor to raise an exception on every
  call.
* Issue a chat request with PII in the body.
* Assert the upstream received the ORIGINAL body (the
  PII in plaintext).
* Assert the gateway returned 200 (didn't 5xx the caller).
* Assert the ``pii_fail_open_counter`` incremented by 1.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.metrics import pii_fail_open_counter

from tests.integration._critical_path_base import CriticalPathTestBase


VALID_ID = "11010119900101004X"


class TestCriticalPath2_5(CriticalPathTestBase):
    """PII Fail-Open — detector 抛异常不阻断."""

    def setUp(self):
        super().setUp()
        # Snapshot the counter at test start so we can compute the
        # delta on assertion (other tests in the suite also increment
        # this counter).
        self._counter_before = self.counter_value(pii_fail_open_counter)

    def test_detector_raises_passes_body_through(self):
        self.install_call_upstream(self.make_echo_upstream())

        async def _explode(trace_id, text):
            raise RuntimeError("simulated detector crash")

        # Patch at the call site in chat.py (it imports ``redact``
        # by name; we have to patch the binding in chat's namespace).
        with patch("app.api.chat.redact", new=_explode):
            r = self.post(
                body={
                    "model": "qwen-max",
                    "messages": [
                        {
                            "role": "user",
                            "content": f"客户 {VALID_ID} 想知道余额",
                        }
                    ],
                },
                headers={"X-Trace-Id": "01HX2EESCENARIO2500000"},
            )
        # 1. Gateway returned 200 (didn't 5xx the caller).
        self.assertEqual(r.status_code, 200, r.text)
        # 2. Upstream received the ORIGINAL body (PII in plaintext).
        sent = self.upstream_received()
        sent_content = sent["messages"][-1]["content"]
        self.assertIn(VALID_ID, sent_content)
        # 3. pii_fail_open_counter incremented by exactly 1.
        delta = self.counter_value(pii_fail_open_counter) - self._counter_before
        self.assertEqual(
            delta, 1, msg=f"expected counter +1, got +{delta}"
        )


if __name__ == "__main__":
    unittest.main()
