"""Critical-path e2e 2.1 — 身份证 脱敏 + 还原 round trip.

End-to-end through the chat endpoint:

1. Caller sends a body containing a valid 身份证 (GB 11643-1999
   mod-11 check passes).
2. Gateway's PII redactor swaps the ID for a typed placeholder
   ``[身份证_<4hex>]`` and writes the placeholder→original map
   to fakeredis.
3. Gateway forwards the redacted body to the LLM upstream
   (a fake httpx response that echoes the body).
4. Gateway runs the reverser on the LLM response, swapping the
   placeholder back to the original ID.
5. The final response to the caller contains the original ID
   (not the placeholder).

This is the eng-review #2 critical-path coverage lock-in for
the paul 财务月报 workflow (PII isolation: 身份证 is the
most-referenced PII type in the financial reporting use case).
"""

from __future__ import annotations

import unittest

from tests.integration._critical_path_base import CriticalPathTestBase


VALID_ID = "11010119900101004X"  # GB 11643-1999 mod-11 valid fixture


class TestCriticalPath2_1(CriticalPathTestBase):
    """身份证 脱敏 + 还原 e2e."""

    def test_id_card_redact_and_reverse_round_trip(self):
        # LLM upstream echoes the user content with a fixed prefix.
        self.install_call_upstream(self.make_echo_upstream())
        r = self.post(
            body={
                "model": "qwen-max",
                "messages": [
                    {
                        "role": "user",
                        "content": f"客户 {VALID_ID} 已确认",
                    }
                ],
            },
            headers={"X-Trace-Id": "01HX2EESCENARIO2100000"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        # 1. Upstream received the placeholder, NOT the original ID.
        sent = self.upstream_received()
        sent_content = sent["messages"][-1]["content"]
        self.assertNotIn(VALID_ID, sent_content)
        self.assertIn("[身份证_", sent_content)
        # 2. Response body contains the original ID (reverser ran).
        resp = r.json()
        resp_content = resp["choices"][0]["message"]["content"]
        self.assertIn(VALID_ID, resp_content)
        # 3. Response doesn't contain any placeholder.
        self.assertNotIn("[身份证_", resp_content)


if __name__ == "__main__":
    unittest.main()
