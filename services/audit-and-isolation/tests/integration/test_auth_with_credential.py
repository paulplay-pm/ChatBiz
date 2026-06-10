"""Integration test for ``verify_service_token`` against a mocked
credential service.

The unit tests (test_auth.py) verify the response-handling logic.
This integration test exercises the same code path but uses a
mock that mimics the *real* credential service's response shape
(``{"service_id": "..."}``) to make sure the gateway can decode
the response the way the production service sends it.

We don't use respx/httpx_mock because neither is in the
project's dev-extra dependencies. The mock is a tiny async
context manager — see the unit test for the shape; this test
exercises the production-shaped success path.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from app.auth import verify_service_token


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _CredentialServiceMock:
    """Simulates a credential service that returns a known
    ``service_id`` for one specific token.

    The gateway's verify call posts ``{"token": ..., "audience": ...}``
    to ``/v1/auth/verify``; we just echo back a fixed identity.
    """

    def __init__(self, service_id: str = "svc-paul-integration"):
        self.service_id = service_id
        self.call_count = 0

    def __call__(self, *args, **kwargs):
        # Return a context manager that, when entered, yields a
        # fake client whose ``post`` returns the canned response.
        client = self

        class _Ctx:
            async def __aenter__(self_inner):
                return client

            async def __aexit__(self_inner, *exc):
                return None

        return _Ctx()

    async def post(self, url, json=None):
        self.call_count += 1
        resp = MagicMock()
        resp.status_code = 200
        resp.json = MagicMock(return_value={"service_id": self.service_id})
        return resp


class TestAuthWithCredential(unittest.TestCase):
    """End-to-end shape check: gateway ↔ credential service."""

    def test_returns_service_id_from_credential(self):
        mock = _CredentialServiceMock(service_id="svc-paul")
        with patch("app.auth.httpx.AsyncClient", new=mock):
            result = _run(verify_service_token("Bearer integration.token"))
        self.assertEqual(result, "svc-paul")
        # The mock recorded exactly one call (no retries on success)
        self.assertEqual(mock.call_count, 1)

    def test_passes_audience_in_request_body(self):
        """Verify the gateway tags the request with the
        correct audience (eng-review #1 lock-in: only the
        audit-and-isolation audience is accepted)."""
        captured = {}

        async def _capture_post(url, json=None):
            captured["url"] = url
            captured["json"] = json
            resp = MagicMock()
            resp.status_code = 200
            resp.json = MagicMock(return_value={"service_id": "x"})
            return resp

        client = MagicMock()
        client.post = _capture_post

        class _Ctx:
            async def __aenter__(self_inner):
                return client

            async def __aexit__(self_inner, *exc):
                return None

        with patch("app.auth.httpx.AsyncClient", return_value=_Ctx()):
            _run(verify_service_token("Bearer t"))
        self.assertIn("/v1/auth/verify", captured["url"])
        self.assertEqual(captured["json"]["audience"], "audit-and-isolation")
        self.assertEqual(captured["json"]["token"], "t")


if __name__ == "__main__":
    unittest.main()
