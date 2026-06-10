"""Critical-path e2e 2.2 — 手机 / 银行卡 边界.

The mobile rule (11 digits, ``1[3-9]\\d{9}``) and the bank-card
rule (16-19 digits, Luhn-validated) are the most-frequently
false-positive-prone PII rules. This test exercises both
boundaries:

* **False-positive guard 1** — a 10-digit number
  (``010-12345``, mocked as ``01012345``) must NOT trigger the
  mobile rule (too short).
* **True positive 1** — a valid 11-digit mobile
  (``13800138000``) MUST trigger the mobile rule and be
  replaced with ``[手机_<4hex>]``.
* **False-positive guard 2** — a 16-digit number that
  fails the Luhn check must NOT trigger the bank-card rule.
* **True positive 2** — a Luhn-valid 16-digit card number
  must trigger the bank-card rule.

The Luhn-valid card number ``4242424242424242`` is the public
Visa test card; it is universally used in PII fixtures.
"""

from __future__ import annotations

import unittest

from tests.integration._critical_path_base import CriticalPathTestBase

# 10-digit sequence that LOOKS like a partial mobile but is one
# digit too short — must NOT match.
SHORT_NUMBER = "01012345"

# Valid 11-digit mobile (well-known test fixture).
VALID_MOBILE = "13800138000"

# Luhn-FAILING 16-digit number (just consecutive digits).
LUHN_FAIL_CARD = "1234567890123456"

# Luhn-VALID 16-digit card (public Visa test fixture).
VALID_CARD = "4242424242424242"


class TestCriticalPath2_2(CriticalPathTestBase):
    """手机 / 银行卡 边界."""

    def test_mobile_and_card_boundaries(self):
        self.install_call_upstream(self.make_echo_upstream())
        r = self.post(
            body={
                "model": "qwen-max",
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"电话 {SHORT_NUMBER}, 真实手机 {VALID_MOBILE}, "
                            f"假卡 {LUHN_FAIL_CARD}, 真卡 {VALID_CARD}"
                        ),
                    }
                ],
            },
            headers={"X-Trace-Id": "01HX2EESCENARIO2200000"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        # 1. Short number did NOT trigger mobile rule.
        sent = self.upstream_received()
        sent_content = sent["messages"][-1]["content"]
        self.assertIn(SHORT_NUMBER, sent_content)
        # 2. Valid mobile WAS replaced.
        self.assertNotIn(VALID_MOBILE, sent_content)
        self.assertIn("[手机_", sent_content)
        # 3. Luhn-FAILING card did NOT trigger bank-card rule.
        # (The 16-digit Luhn-FAILING sequence must be passed through
        # verbatim; the 16-digit Luhn-VALID card got redacted, so
        # we check the FAILING one is still in the body and that
        # there is exactly one [银行卡_] placeholder — corresponding
        # to the valid card only.)
        self.assertIn(LUHN_FAIL_CARD, sent_content)
        self.assertEqual(sent_content.count("[银行卡_"), 1)
        # 4. Luhn-valid card WAS replaced.
        self.assertNotIn(VALID_CARD, sent_content)
        # 5. Response contains the originals.
        resp = r.json()
        resp_content = resp["choices"][0]["message"]["content"]
        self.assertIn(VALID_MOBILE, resp_content)
        self.assertIn(VALID_CARD, resp_content)


if __name__ == "__main__":
    unittest.main()
