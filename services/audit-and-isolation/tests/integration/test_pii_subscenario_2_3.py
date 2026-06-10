"""Critical-path e2e 2.3 — 邮箱 / 信用代码 / 营收 3 类 PII.

The remaining three PII rule families: email, USCC (统一社会信用
代码), and 营收 amount. The first two are regex-only (no
secondary validation, no Luhn/ID-card check). The 营收 rule
matches a Chinese-style monetary amount string like
``"营收 1,234,567.89 元"``.

We test:

* Email regex match — ``zhang@example.com`` becomes
  ``[邮箱_<4hex>]``.
* USCC regex match — 18 alphanumeric chars from the GB 32100
  alphabet (we use ``91110000600037341L``, a real but
  fictitious placeholder USCC).
* 营收 regex match — the amount phrase becomes
  ``[营收金额_<4hex>]``.

All three types are detected in a single request and the
redactor writes a single map to Redis. The reverser swaps all
three placeholders back on the response side.
"""

from __future__ import annotations

import unittest

from tests.integration._critical_path_base import CriticalPathTestBase

VALID_EMAIL = "zhang@example.com"
# USCC: 18-char GB 32100-2015 alphabet (no I, O, Q, S, V, Z).
VALID_USCC = "91110000600037341L"
REVENUE_PHRASE = "营收 1,234,567.89 元"


class TestCriticalPath2_3(CriticalPathTestBase):
    """邮箱 / 信用代码 / 营收 3 类."""

    def test_email_uscc_revenue(self):
        self.install_call_upstream(self.make_echo_upstream())
        r = self.post(
            body={
                "model": "qwen-max",
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"邮箱 {VALID_EMAIL} 信用代码 {VALID_USCC} "
                            f"{REVENUE_PHRASE}"
                        ),
                    }
                ],
            },
            headers={"X-Trace-Id": "01HX2EESCENARIO2300000"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        sent = self.upstream_received()
        sent_content = sent["messages"][-1]["content"]
        # 1. Email replaced.
        self.assertNotIn(VALID_EMAIL, sent_content)
        self.assertIn("[邮箱_", sent_content)
        # 2. USCC replaced.
        self.assertNotIn(VALID_USCC, sent_content)
        self.assertIn("[信用代码_", sent_content)
        # 3. Revenue replaced.
        self.assertNotIn(REVENUE_PHRASE, sent_content)
        self.assertIn("[营收金额_", sent_content)
        # 4. Response contains the originals.
        resp = r.json()
        resp_content = resp["choices"][0]["message"]["content"]
        self.assertIn(VALID_EMAIL, resp_content)
        self.assertIn(VALID_USCC, resp_content)
        self.assertIn(REVENUE_PHRASE, resp_content)


if __name__ == "__main__":
    unittest.main()
