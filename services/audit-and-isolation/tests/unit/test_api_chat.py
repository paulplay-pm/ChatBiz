"""Unit tests for the ``POST /v1/chat/completions`` endpoint's
*request-validation* surface — the bits FastAPI handles before
our pipeline runs.

5 cases the plan calls out:

* Invalid JSON body → 422
* Body > 1 MB → 413
* Model not in routing table → 400
* Missing/invalid ``X-Trace-Id`` header → 422

Plus a few sanity checks for the headers we *require*:

* Missing ``X-Model-Kind`` → 422
* Non-Bearer ``Authorization`` → 401 (auth runs first)
* Missing ``Authorization`` → 401

We mock out everything past the auth + header + body checks
(``verify_service_token`` returns a fixed service_id, the
routing table is patched). The deep-pipeline tests live in
``test_e2e_4_scenarios.py``.
"""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Set required env vars BEFORE importing the app so config validates.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x")
os.environ.setdefault("REDIS_URL", "redis://x")
os.environ.setdefault("CREDENTIAL_SERVICE_URL", "http://x")

from fastapi.testclient import TestClient

from app.main import app


# Build the client once; per-test patches modify the live state.
client = TestClient(app)


def _override_auth(service_id: str = "svc-test"):
    """Replace ``verify_service_token`` dependency with a fixed
    service_id. Used by tests that need to bypass real auth."""

    async def _stub(authorization=None):
        return service_id

    return _stub


class TestChatEndpointValidation(unittest.TestCase):
    """The 5-case matrix from the plan."""

    def setUp(self):
        # Reset the outbox so each test sees a clean queue.
        from app.audit.writer import reset_outbox_for_tests

        reset_outbox_for_tests()
        # Patch verify_service_token at the call site (app.api.chat) so
        # the tests don't need to run a real credential service.
        self._auth_patcher = patch(
            "app.api.chat.verify_service_token",
            new=AsyncMock(return_value="svc-test"),
        )
        self._auth_patcher.start()
        # Patch the routing table loader to a known entry.
        from app.routing import dispatcher as dispatcher_mod

        self._routing_patcher = patch.object(
            dispatcher_mod,
            "get_routing",
            new=AsyncMock(
                return_value={
                    "model_kind": "public",
                    "upstream_base_url": "https://upstream.example.com",
                    "upstream_path": "/v1/chat/completions",
                    "timeout_ms": 30000,
                }
            ),
        )
        self._routing_patcher.start()
        # Patch the LLM client so tests don't hit a real upstream.
        from app.llm import client as llm_client_mod

        async def _fake_call_upstream(base_url, path, body, headers):
            resp = MagicMock()
            resp.status_code = 200
            resp.json = MagicMock(
                return_value={
                    "id": "cmpl-x",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "hello",
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                }
            )
            return resp

        self._llm_patcher = patch.object(
            llm_client_mod, "call_upstream", new=_fake_call_upstream
        )
        self._llm_patcher.start()
        # Patch credential client so the in-memory cache lookup doesn't
        # try the real credential service.
        from app import credential_client as cred_mod

        self._cred_patcher = patch.object(
            cred_mod, "get_llm_api_key", new=AsyncMock(return_value="sk-fake")
        )
        self._cred_patcher.start()
        # PII redactor: also patch so we don't need Redis.
        from app.pii import redactor as redactor_mod

        async def _fake_redact(trace_id, text):
            return text, {}, []

        self._redact_patcher = patch.object(
            redactor_mod, "redact", new=_fake_redact
        )
        self._redact_patcher.start()
        # PII reverser: same reason.
        from app.pii import reverser as reverser_mod

        async def _fake_reverse(trace_id, text):
            return text

        self._reverse_patcher = patch.object(
            reverser_mod, "reverse", new=_fake_reverse
        )
        self._reverse_patcher.start()

    def tearDown(self):
        for p in (
            self._auth_patcher,
            self._routing_patcher,
            self._llm_patcher,
            self._cred_patcher,
            self._redact_patcher,
            self._reverse_patcher,
        ):
            p.stop()

    def _valid_body(self) -> dict:
        return {
            "model": "qwen-max",
            "messages": [{"role": "user", "content": "hi"}],
        }

    def test_invalid_json_body_422(self):
        """Body is not valid JSON → 422 from FastAPI's parser."""
        r = client.post(
            "/v1/chat/completions",
            content="not json",
            headers={
                "Authorization": "Bearer t",
                "X-Trace-Id": "01HXCHATUSER000000000000",
                "X-Model-Kind": "public",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(r.status_code, 422)

    def test_body_too_large_413(self):
        """Body > 1 MB → 413."""
        big_msg = "x" * (1_200_000)
        body = self._valid_body()
        body["messages"][0]["content"] = big_msg
        r = client.post(
            "/v1/chat/completions",
            content=json.dumps(body),
            headers={
                "Authorization": "Bearer t",
                "X-Trace-Id": "01HXCHATUSER000000000000",
                "X-Model-Kind": "public",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(r.status_code, 413)

    def test_model_not_in_routing_table_400(self):
        """Routing dispatcher raises → 400."""
        from app.routing.dispatcher import RoutingError

        async def _raise_route(model, header):
            raise RoutingError("model not found in routing table: bogus")

        with patch("app.api.chat.resolve_route", new=_raise_route):
            r = client.post(
                "/v1/chat/completions",
                json=self._valid_body(),
                headers={
                    "Authorization": "Bearer t",
                    "X-Trace-Id": "01HXCHATUSER000000000000",
                    "X-Model-Kind": "public",
                },
            )
        self.assertEqual(r.status_code, 400)

    def test_missing_trace_id_422(self):
        """No ``X-Trace-Id`` → 422 from FastAPI's Header validator."""
        r = client.post(
            "/v1/chat/completions",
            json=self._valid_body(),
            headers={
                "Authorization": "Bearer t",
                "X-Model-Kind": "public",
            },
        )
        self.assertEqual(r.status_code, 422)

    def test_too_short_trace_id_422(self):
        """Trace id < 8 chars → 422."""
        r = client.post(
            "/v1/chat/completions",
            json=self._valid_body(),
            headers={
                "Authorization": "Bearer t",
                "X-Trace-Id": "short",
                "X-Model-Kind": "public",
            },
        )
        self.assertEqual(r.status_code, 422)

    def test_missing_authorization_401(self):
        """No ``Authorization`` header → 401 from auth."""
        # Stop the auth patcher for this test specifically, so the
        # real verify_service_token runs.
        self._auth_patcher.stop()
        try:
            r = client.post(
                "/v1/chat/completions",
                json=self._valid_body(),
                headers={
                    "X-Trace-Id": "01HXCHATUSER000000000000",
                    "X-Model-Kind": "public",
                },
            )
            self.assertEqual(r.status_code, 401)
        finally:
            self._auth_patcher.start()

    def test_missing_model_kind_422(self):
        """No ``X-Model-Kind`` → 422."""
        r = client.post(
            "/v1/chat/completions",
            json=self._valid_body(),
            headers={
                "Authorization": "Bearer t",
                "X-Trace-Id": "01HXCHATUSER000000000000",
            },
        )
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
