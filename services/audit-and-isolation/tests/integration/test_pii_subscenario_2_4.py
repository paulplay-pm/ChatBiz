"""Critical-path e2e 2.4 — 响应侧还原 占位符一致性.

The reverser's contract is: every placeholder in the response
text is replaced with the SAME original value as was redacted
on the request side, for the SAME trace-id. This test verifies
that the placeholder→original map is stable across multiple
calls sharing a trace id — even when the upstream LLM "echoes"
the placeholder back, the reverser swaps it to the original
verbatim.

Why this matters: the data-isolation gateway's user-visible
contract is that PII the caller sent in the request reappears
in the response. If a placeholder gets accidentally mapped to
the wrong value, the caller sees the wrong PII — a silent
correctness bug with security implications.

Test shape:

* Two calls on the same ``X-Trace-Id``, both with the same
  PII in the body. The second call's redactor reuses the
  same Redis key (``redact:trace:<trace_id>``) but writes a
  fresh map. The reverser then reads the latest map and
  swaps placeholders back to originals. We assert the
  *original* ID appears in both responses.
"""

from __future__ import annotations

import unittest

from tests.integration._critical_path_base import CriticalPathTestBase


VALID_ID = "11010119900101004X"


class TestCriticalPath2_4(CriticalPathTestBase):
    """响应侧还原 — 同 trace 占位符前后一致."""

    def test_two_calls_same_trace_consistent_reverse(self):
        self.install_call_upstream(self.make_echo_upstream())
        # First call: redactor writes a map under the trace_id.
        r1 = self.post(
            body={
                "model": "qwen-max",
                "messages": [
                    {
                        "role": "user",
                        "content": f"first call id: {VALID_ID}",
                    }
                ],
            },
            headers={"X-Trace-Id": "01HX2EESCENARIO2400000"},
        )
        self.assertEqual(r1.status_code, 200, r1.text)
        # Second call on the SAME trace-id.
        r2 = self.post(
            body={
                "model": "qwen-max",
                "messages": [
                    {
                        "role": "user",
                        "content": f"second call id: {VALID_ID}",
                    }
                ],
            },
            headers={"X-Trace-Id": "01HX2EESCENARIO2400000"},
        )
        self.assertEqual(r2.status_code, 200, r2.text)
        # Both responses contain the original ID (not the placeholder).
        for r in (r1, r2):
            content = r.json()["choices"][0]["message"]["content"]
            self.assertIn(VALID_ID, content)
            self.assertNotIn("[身份证_", content)
        # Both upstream calls received placeholders, not originals.
        # ``_received_bodies`` accumulates across both requests.
        bodies = self._received_bodies
        self.assertEqual(len(bodies), 2)
        for body in bodies:
            sent = body["messages"][-1]["content"]
            self.assertIn("[身份证_", sent)
            self.assertNotIn(VALID_ID, sent)


if __name__ == "__main__":
    unittest.main()
