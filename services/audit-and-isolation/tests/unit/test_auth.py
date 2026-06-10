"""Unit tests for ``app.auth.verify_service_token``.

5 cases the plan calls out:

* valid token → returns the credential service's ``service_id``
* no ``Authorization`` header → 401
* ``Authorization`` without ``Bearer `` → 401
* credential service unreachable → 503
* token rejected (4xx from credential service) → 401

The credential service is mocked by patching
``httpx.AsyncClient`` so we don't need a live service to run the
tests. The mock returns either a fake ``service_id`` (success
case) or raises a fake ``HTTPError`` (unreachable case).
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock, patch

import httpx

from app.auth import verify_service_token


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _FakeAsyncClient:
    """Minimal httpx.AsyncClient stand-in for the verify call.

    The ``__aenter__`` returns self; ``post`` returns the response
    configured at construction time. We can't use ``MagicMock``
    directly because ``httpx.AsyncClient`` is normally used as an
    async context manager.
    """

    def __init__(self, *, status_code=200, json_data=None, raise_exc=None, timeout=5.0):
        self._status = status_code
        self._json = json_data or {}
        self._raise = raise_exc
        self._timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, json=None):
        if self._raise is not None:
            raise self._raise
        resp = MagicMock()
        resp.status_code = self._status
        resp.json = MagicMock(return_value=self._json)
        return resp


class TestVerifyServiceToken(unittest.TestCase):
    """The 5-case matrix from the plan."""

    def test_valid_token_returns_service_id(self):
        client = _FakeAsyncClient(status_code=200, json_data={"service_id": "svc-paul"})
        with patch("app.auth.httpx.AsyncClient", return_value=client):
            result = _run(verify_service_token("Bearer abc.def.ghi"))
        self.assertEqual(result, "svc-paul")

    def test_missing_authorization_header_401(self):
        with self.assertRaises(Exception) as ctx:
            _run(verify_service_token(None))
        # FastAPI's HTTPException is what we raise
        self.assertEqual(ctx.exception.status_code, 401)

    def test_non_bearer_scheme_401(self):
        with self.assertRaises(Exception) as ctx:
            _run(verify_service_token("Basic dXNlcjpwYXNz"))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_credential_service_unreachable_503(self):
        client = _FakeAsyncClient(raise_exc=httpx.ConnectError("conn refused"))
        with patch("app.auth.httpx.AsyncClient", return_value=client):
            with self.assertRaises(Exception) as ctx:
                _run(verify_service_token("Bearer abc.def.ghi"))
        self.assertEqual(ctx.exception.status_code, 503)

    def test_invalid_token_401(self):
        # credential service returned 401 (token rejected)
        client = _FakeAsyncClient(status_code=401, json_data={"detail": "bad token"})
        with patch("app.auth.httpx.AsyncClient", return_value=client):
            with self.assertRaises(Exception) as ctx:
                _run(verify_service_token("Bearer wrong.token.value"))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_empty_authorization_401(self):
        # Empty string is treated as missing
        with self.assertRaises(Exception) as ctx:
            _run(verify_service_token(""))
        self.assertEqual(ctx.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
