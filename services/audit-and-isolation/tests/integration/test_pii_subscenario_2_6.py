"""Critical-path e2e 2.6 — 上游 timeout 完整 e2e.

The data-isolation gateway's 50 ms p99 SLO depends on the
upstream LLM provider responding within the 30 s
``upstream_timeout_ms`` budget. If the upstream hangs
beyond that, the gateway's LLM client re-raises
:class:`UpstreamTimeout` (after the internal 200 ms × 1 retry).
The chat handler maps that to HTTP 504 so the caller can
distinguish "upstream is slow" from "upstream is broken"
(502).

This test drives the typed :class:`UpstreamTimeout` through
the chat pipeline via a fake ``call_upstream`` — the same
shape ``call_upstream`` re-raises after a 30 s+ hang, so the
chat handler's typed catch fires.

Test shape:

* Replace ``call_upstream`` with a fake that raises
  ``UpstreamTimeout``.
* Issue a chat request.
* Assert the gateway returns 504.
"""

from __future__ import annotations

import unittest

from app.errors import UpstreamTimeout

from tests.integration._critical_path_base import CriticalPathTestBase


class TestCriticalPath2_6(CriticalPathTestBase):
    """上游 timeout 完整 e2e."""

    def test_upstream_timeout_returns_504(self):
        async def _timeout(base_url, path, body, headers):
            # The same typed error ``call_upstream`` re-raises
            # after a 30s+ hang on the upstream.
            raise UpstreamTimeout("simulated 30s timeout")

        self.install_call_upstream(_timeout)
        r = self.post(
            body={
                "model": "qwen-max",
                "messages": [{"role": "user", "content": "hi"}],
            },
            headers={"X-Trace-Id": "01HX2EESCENARIO2600000"},
        )
        # 504 Gateway Timeout — the standard mapping for upstream
        # timeout in the chat handler.
        self.assertEqual(r.status_code, 504, r.text)


if __name__ == "__main__":
    unittest.main()
