"""Shared fixtures for the critical-path e2e tests.

Each test file (test_pii_subscenario_2_X.py) imports the
:class:`CriticalPathTestBase` class from here, which sets up
the test client with auth / routing / credential / LLM
upstream all stubbed, and fakeredis for the PII map
round-trip.

Pattern:

    class TestSomething(CriticalPathTestBase):
        def test_x(self):
            self.install_call_upstream(...)
            r = self.post(...)

The base class also exposes a helper to swap the LLM upstream
response (per test) and a counter getter for the prometheus
counters.
"""

from __future__ import annotations

import os
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

# Env-var defaults — these tests don't talk to real PG / Redis /
# credential service, but ``Settings`` still validates at import.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x")
os.environ.setdefault("REDIS_URL", "redis://x")
os.environ.setdefault("CREDENTIAL_SERVICE_URL", "http://x")

import fakeredis.aioredis  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import redis_client  # noqa: E402
from app.main import app  # noqa: E402


def _public_route_entry() -> dict:
    """Default public route — no PII skip."""
    return {
        "model_kind": "public",
        "upstream_base_url": "https://upstream.example.com",
        "upstream_path": "/v1/chat/completions",
        "timeout_ms": 30000,
        "skip_pii": False,
    }


def _private_bypass_route_entry() -> dict:
    """Private + bypass route — PII skipped."""
    return {
        "model_kind": "private",
        "upstream_base_url": "https://private.example.com",
        "upstream_path": "/v1/chat/completions",
        "timeout_ms": 30000,
        "skip_pii": True,
    }


class CriticalPathTestBase(unittest.TestCase):
    """Shared base for the 8 critical-path e2e tests.

    Subclasses get a fully-stubbed FastAPI ``TestClient`` plus
    a small set of helpers:

    * :meth:`install_call_upstream` — replace the LLM upstream
      call with a fake. The fake may raise, return a 200, or
      return a 5xx — whatever the test needs.
    * :meth:`install_route` — replace the routing table.
    * :meth:`received_upstream_bodies` — list of bodies the
      fake upstream saw (only the last call's body, since
      critical-path tests run a single request per test method).
    * :meth:`post` — issue a POST with the standard headers,
      customised for the per-test scenario.
    """

    def setUp(self) -> None:
        # Reset singletons that are mutated by the chat pipeline.
        from app.audit.writer import reset_outbox_for_tests

        reset_outbox_for_tests()
        # fakeredis for the PII map round-trip.
        redis_client.reset_pool_for_tests()
        self._fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        redis_client.get_redis = lambda: self._fake_redis
        # Auth → fixed service_id.
        self._auth_patcher = patch(
            "app.api.chat.verify_service_token",
            new=AsyncMock(return_value="svc-paul"),
        )
        self._auth_patcher.start()
        # Credential → fixed key.
        self._cred_patcher = patch(
            "app.api.chat.get_llm_api_key",
            new=AsyncMock(return_value="sk-fake"),
        )
        self._cred_patcher.start()
        # Default route: public, no bypass.
        self._route_patcher = patch(
            "app.routing.dispatcher.get_routing",
            new=AsyncMock(return_value=_public_route_entry()),
        )
        self._route_patcher.start()
        # LLM upstream — placeholder, replaced by install_call_upstream.
        self._received_bodies: list[dict] = []
        self._llm_patcher: Any = None
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self._auth_patcher.stop()
        self._cred_patcher.stop()
        self._route_patcher.stop()
        if self._llm_patcher is not None:
            self._llm_patcher.stop()

    # ----------------------------------------------------------- helpers

    def install_route(self, entry: dict) -> None:
        """Replace the routing table with ``entry`` for this test."""
        self._route_patcher.stop()
        self._route_patcher = patch(
            "app.routing.dispatcher.get_routing",
            new=AsyncMock(return_value=entry),
        )
        self._route_patcher.start()

    def install_call_upstream(self, fake_call) -> None:
        """Replace the LLM upstream call with ``fake_call``.

        ``fake_call`` is an async function with signature
        ``(base_url, path, body, headers) -> httpx.Response | raise``.
        """
        if self._llm_patcher is not None:
            self._llm_patcher.stop()
        self._llm_patcher = patch(
            "app.api.chat.call_upstream", new=fake_call
        )
        self._llm_patcher.start()

    def make_echo_upstream(self) -> Any:
        """Build an LLM-fake that echoes the user content with a prefix.

        Useful for PII reverse tests — the response contains the
        same string the user sent, so the reverser has something
        to swap.
        """

        async def _echo(base_url, path, body, headers):
            self._received_bodies.append(body)
            user_msg = body["messages"][-1]["content"]
            resp = MagicMock()
            resp.status_code = 200
            resp.json = MagicMock(
                return_value={
                    "id": "cmpl-echo",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": f"echo: {user_msg}",
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                }
            )
            return resp

        return _echo

    def post(self, body: dict, headers: dict | None = None) -> Any:
        """POST ``/v1/chat/completions`` with the standard headers.

        ``headers`` overrides the default (Bearer t, public, 24-char
        trace id). Pass only the keys you need to change.
        """
        default_headers = {
            "Authorization": "Bearer t",
            "X-Trace-Id": "01HXE2ECRIT01PATH00000000",
            "X-Model-Kind": "public",
        }
        if headers:
            default_headers.update(headers)
        return self.client.post(
            "/v1/chat/completions",
            json=body,
            headers=default_headers,
        )

    def upstream_received(self) -> dict | None:
        """Return the last body the fake upstream saw, or None."""
        return self._received_bodies[-1] if self._received_bodies else None

    def counter_value(self, counter) -> float:
        """Read a Prometheus counter's current value.

        Works for any of the counters in :mod:`app.metrics` — the
        test asserts the counter incremented as expected.
        """
        return counter._value.get()  # noqa: SLF001 (intentional: private API)
