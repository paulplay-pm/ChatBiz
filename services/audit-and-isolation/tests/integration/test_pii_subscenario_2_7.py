"""Critical-path e2e 2.7 — credential service 不可达 完整 e2e.

The credential service is the source of truth for which
LLM provider API key to use per model. If the credential
service is unreachable, the gateway MUST fail-closed
(return 503 to the caller) — never call the upstream
LLM with a missing or empty key. This is the conservative
direction for the credential path: the user gets a 503 and
a clear error_class tag in the body; the alternative
(forwarding a request to the upstream with a placeholder
key) would leak the call to a third-party LLM provider
unauthenticated, which is a worse security posture.

Test shape:

* Replace ``get_llm_api_key`` (called by the chat handler
  to fetch the upstream API key) with a fake that raises
  a generic exception (mirroring the production path where
  the credential client re-raises after the single retry).
* Issue a chat request.
* Assert the gateway returns 503.
* Assert the ``credential_unavailable_counter`` incremented.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.metrics import credential_unavailable_counter

from tests.integration._critical_path_base import CriticalPathTestBase


class TestCriticalPath2_7(CriticalPathTestBase):
    """credential service 不可达."""

    def setUp(self):
        super().setUp()
        self._counter_before = self.counter_value(credential_unavailable_counter)

    def test_credential_down_returns_503(self):
        # Replace the chat module's binding of get_llm_api_key with
        # an always-raising stub. The credential_client's retry
        # already ran in production; we just simulate the
        # "after retry, still failed" path by raising once.
        async def _boom(model_name, token):
            raise RuntimeError("credential service down")

        with patch("app.api.chat.get_llm_api_key", new=_boom):
            r = self.post(
                body={
                    "model": "qwen-max",
                    "messages": [{"role": "user", "content": "hi"}],
                },
                headers={"X-Trace-Id": "01HX2EESCENARIO2700000"},
            )
        # 503 — the chat handler maps credential failures to 503.
        self.assertEqual(r.status_code, 503, r.text)
        # credential_unavailable_counter incremented by 1.
        delta = (
            self.counter_value(credential_unavailable_counter)
            - self._counter_before
        )
        self.assertEqual(
            delta, 1, msg=f"expected counter +1, got +{delta}"
        )


if __name__ == "__main__":
    unittest.main()
