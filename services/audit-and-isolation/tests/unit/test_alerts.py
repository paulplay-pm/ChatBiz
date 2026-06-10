"""Unit tests for :mod:`app.alerts`.

The alert webhook is a side effect — failures must NEVER block the
chat pipeline. We verify:

* A successful POST is issued with the correct URL + JSON body.
* A network error on the POST is caught and logged (the function
  returns ``None`` and does not raise).
* A 5xx response from the webhook is also swallowed (the
  ``AsyncClient.post`` itself succeeds — the webhook server
  simply returns 5xx — so we treat that as a non-fatal path).

We mock ``httpx.AsyncClient`` with a context manager stand-in that
records every call and replays a configured response (status code or
exception). The mocking pattern mirrors
``tests/unit/test_credential_client.py`` so the test is consistent
with the rest of the suite.
"""

from __future__ import annotations

import asyncio
import logging
import unittest
from unittest.mock import MagicMock, patch

import httpx

from app.alerts import fire_alert


def _run(coro):
    """Tiny ``asyncio.run`` wrapper — see ``test_credential_client.py``."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _Recorder:
    """Records every ``httpx.AsyncClient.post`` call.

    Replays a configured status code or raises a configured exception.
    Mirrors ``_PostRecorder`` in ``test_credential_client.py`` but
    trimmed for the alerts surface (no body assertion needed beyond
    the json= kwarg).
    """

    def __init__(self, status: int = 200, raise_exc: Exception | None = None):
        self.status = status
        self.raise_exc = raise_exc
        self.calls: list[tuple[str, dict]] = []

    def make_client(self):
        rec = self

        class _Client:
            async def post(inner_self, url, json=None):
                rec.calls.append((url, json))
                if rec.raise_exc is not None:
                    raise rec.raise_exc
                resp = MagicMock()
                resp.status_code = rec.status
                return resp

        class _Ctx:
            async def __aenter__(self_inner):
                return _Client()

            async def __aexit__(self_inner, *exc):
                return None

        return _Ctx()


class TestFireAlert(unittest.TestCase):
    """The 3-case matrix from the plan."""

    def test_successful_post_sends_correct_body(self):
        rec = _Recorder(status=200)
        with patch(
            "app.alerts.httpx.AsyncClient",
            new=lambda *a, **kw: rec.make_client(),
        ):
            # Function returns None on success.
            result = _run(
                fire_alert(
                    "warning",
                    "PiiFailOpen",
                    {"trace_id": "t-1", "model": "qwen-max"},
                )
            )
        self.assertIsNone(result)
        # Exactly one POST issued.
        self.assertEqual(len(rec.calls), 1)
        url, body = rec.calls[0]
        # URL is the configured webhook.
        from app.config import get_settings

        self.assertEqual(url, get_settings().alert_webhook_url)
        # Body shape matches the contract.
        self.assertEqual(body["level"], "warning")
        self.assertEqual(body["error_class"], "PiiFailOpen")
        self.assertEqual(body["context"]["trace_id"], "t-1")
        self.assertEqual(body["context"]["model"], "qwen-max")

    def test_network_error_is_swallowed(self):
        rec = _Recorder(raise_exc=httpx.ConnectError("simulated outage"))
        with self.assertLogs("app.alerts", level="WARNING") as cm:
            with patch(
                "app.alerts.httpx.AsyncClient",
                new=lambda *a, **kw: rec.make_client(),
            ):
                # Must NOT raise — alert failures are swallowed.
                result = _run(
                    fire_alert("critical", "CredentialServiceDown", {"x": 1})
                )
        self.assertIsNone(result)
        # One POST attempted.
        self.assertEqual(len(rec.calls), 1)
        # A warning was logged with the error_class tag.
        self.assertTrue(
            any("CredentialServiceDown" in line for line in cm.output),
            msg=f"expected CredentialServiceDown in log output, got {cm.output}",
        )

    def test_5xx_response_is_swallowed(self):
        """Webhook server returned 5xx — gateway does not care.

        ``httpx.AsyncClient.post`` itself succeeded; the 5xx is
        data the webhook server logs itself. The gateway's
        responsibility is "the request was made"; the webhook
        server's responsibility is "the request was delivered to
        a human". We assert the call happened and the function
        returned ``None`` (no exception)."""
        rec = _Recorder(status=503)
        with patch(
            "app.alerts.httpx.AsyncClient",
            new=lambda *a, **kw: rec.make_client(),
        ):
            result = _run(fire_alert("info", "TestEvent", {"k": "v"}))
        self.assertIsNone(result)
        self.assertEqual(len(rec.calls), 1)

    def test_timeout_error_is_swallowed(self):
        """TimeoutError (e.g. webhook server hanging > 5 s) is also
        a swallowed failure."""
        rec = _Recorder(raise_exc=httpx.TimeoutException("5s elapsed"))
        with self.assertLogs("app.alerts", level="WARNING"):
            with patch(
                "app.alerts.httpx.AsyncClient",
                new=lambda *a, **kw: rec.make_client(),
            ):
                result = _run(fire_alert("warning", "SlowUpstream", {}))
        self.assertIsNone(result)
        self.assertEqual(len(rec.calls), 1)


if __name__ == "__main__":
    unittest.main()
