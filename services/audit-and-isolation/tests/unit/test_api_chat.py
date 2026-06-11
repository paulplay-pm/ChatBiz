"""Unit tests for the ``POST /v1/chat/completions`` endpoint.

Covers the full 7-class exception taxonomy and validation surface:

* Invalid JSON body -> 422
* Body > 1 MB -> 413
* Model not in routing table -> 400
* Missing/too-short X-Trace-Id -> 422
* Missing X-Model-Kind -> 422
* Missing Authorization -> 401
* HeaderSchema ValueError/TypeError -> 422 (lines 102-103)
* Missing "model" key -> 422 (lines 119-120)
* Non-string message content skip (line 129)
* PII fail-open=False + detector crash -> 503 (line 143)
* Upstream5xx -> 502 (lines 166-168)
* UpstreamRateLimited -> 429 (lines 169-170)
* Generic upstream exception -> 502 (lines 171-173)

We mock auth, routing, credential, LLM client and PII layers.
Deep-pipeline tests live in test_e2e_4_scenarios.py.
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

client = TestClient(app)


class TestChatEndpointValidation(unittest.TestCase):

    def setUp(self):
        from app.audit.writer import reset_outbox_for_tests
        reset_outbox_for_tests()

        # Auth -> fixed service_id.
        # Patch BOTH the source AND the chat module since chat.py
        # does `from app.auth import verify_service_token`.
        self._auth_patcher = patch(
            "app.api.chat.verify_service_token",
            new=AsyncMock(return_value="svc-test"),
        )
        self._auth_patcher.start()

        # Routing -> known public entry.
        # resolve_route imports get_routing; patch at the dispatcher source.
        from app.routing import dispatcher as disp
        self._routing_patcher = patch.object(
            disp, "get_routing",
            new=AsyncMock(return_value={
                "model_kind": "public",
                "upstream_base_url": "https://upstream.example.com",
                "upstream_path": "/v1/chat/completions",
                "timeout_ms": 30000,
            }),
        )
        self._routing_patcher.start()

        # LLM upstream -> 200 echo.  Must patch on app.api.chat (the
        # module that uses call_upstream) since chat.py has its own
        # module-level binding.
        async def _fake_call(base_url, path, body, headers):
            resp = MagicMock()
            resp.status_code = 200
            resp.json = MagicMock(return_value={
                "id": "cmpl-x",
                "choices": [{"message": {"role": "assistant", "content": "hello"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            })
            return resp

        self._llm_patcher = patch(
            "app.api.chat.call_upstream", new=_fake_call
        )
        self._llm_patcher.start()

        # Credential -> fixed key. chat.py imports at module level,
        # so the name bindings in both modules must be patched.
        from app import credential_client as cred_mod
        self._cred_patcher = patch.object(
            cred_mod, "get_llm_api_key",
            new=AsyncMock(return_value="sk-fake"),
        )
        self._cred_patcher.start()
        from app.api import chat as chat_mod
        self._chat_cred_patcher = patch.object(
            chat_mod, "get_llm_api_key",
            new=AsyncMock(return_value="sk-fake"),
        )
        self._chat_cred_patcher.start()

        # PII redactor -> no-op.
        async def _fake_redact(trace_id, text):
            return text, {}, []
        from app.pii import redactor as redact_mod
        self._redact_patcher = patch.object(redact_mod, "redact", new=_fake_redact)
        self._redact_patcher.start()

        # PII reverser -> no-op.
        async def _fake_reverse(trace_id, text):
            return text
        from app.pii import reverser as rev_mod
        self._reverse_patcher = patch.object(rev_mod, "reverse", new=_fake_reverse)
        self._reverse_patcher.start()

        self._patchers = [
            self._auth_patcher, self._routing_patcher, self._llm_patcher,
            self._cred_patcher, self._chat_cred_patcher,
            self._redact_patcher, self._reverse_patcher,
        ]

    def tearDown(self):
        for p in self._patchers:
            p.stop()

    def _valid_body(self):
        return {"model": "qwen-max", "messages": [{"role": "user", "content": "hi"}]}

    def _headers(self, **overrides):
        h = {
            "Authorization": "Bearer t",
            "X-Trace-Id": "01HXCHATUSER000000000000",
            "X-Model-Kind": "public",
        }
        h.update(overrides)
        return h

    # -- Validation surface --------------------------------------------------

    def test_invalid_json_body_422(self):
        r = client.post("/v1/chat/completions", content="not json",
                        headers={**self._headers(), "Content-Type": "application/json"})
        self.assertEqual(r.status_code, 422)

    def test_body_too_large_413(self):
        big_msg = "x" * 1_200_000
        body = self._valid_body()
        body["messages"][0]["content"] = big_msg
        r = client.post("/v1/chat/completions", content=json.dumps(body),
                        headers={**self._headers(), "Content-Type": "application/json"})
        self.assertEqual(r.status_code, 413)

    def test_model_not_in_routing_table_400(self):
        from app.routing.dispatcher import RoutingError
        async def _raise_route(model, header):
            raise RoutingError("not found")
        with patch("app.api.chat.resolve_route", new=_raise_route):
            r = client.post("/v1/chat/completions", json=self._valid_body(),
                            headers=self._headers())
        self.assertEqual(r.status_code, 400)

    def test_missing_trace_id_422(self):
        r = client.post("/v1/chat/completions", json=self._valid_body(),
                        headers={"Authorization": "Bearer t", "X-Model-Kind": "public"})
        self.assertEqual(r.status_code, 422)

    def test_too_short_trace_id_422(self):
        r = client.post("/v1/chat/completions", json=self._valid_body(),
                        headers=self._headers(**{"X-Trace-Id": "short"}))
        self.assertEqual(r.status_code, 422)

    def test_missing_authorization_401(self):
        self._auth_patcher.stop()
        try:
            r = client.post("/v1/chat/completions", json=self._valid_body(),
                            headers={"X-Trace-Id": "01HXCHATUSER000000000000",
                                      "X-Model-Kind": "public"})
            self.assertEqual(r.status_code, 401)
        finally:
            self._auth_patcher.start()

    def test_missing_model_kind_422(self):
        r = client.post("/v1/chat/completions", json=self._valid_body(),
                        headers={"Authorization": "Bearer t",
                                  "X-Trace-Id": "01HXCHATUSER000000000000"})
        self.assertEqual(r.status_code, 422)

    # -- Extended coverage for chat.py missing lines -------------------------

    def test_header_valueerror_422(self):
        """Monkeypatch HeaderSchema to raise ValueError -> 422 (lines 102-103)."""
        from app.models import common as common_mod
        orig_init = common_mod.HeaderSchema.__init__

        def _raise(*a, **kw):
            raise ValueError("simulated")

        common_mod.HeaderSchema.__init__ = _raise
        try:
            r = client.post("/v1/chat/completions", json=self._valid_body(),
                            headers=self._headers())
            self.assertEqual(r.status_code, 422)
        finally:
            common_mod.HeaderSchema.__init__ = orig_init

    def test_missing_model_key_422(self):
        """resolve_route raises KeyError -> 422 (lines 119-120)."""
        async def _raise_keyerror(model, header):
            raise KeyError("model")
        with patch("app.api.chat.resolve_route", new=_raise_keyerror):
            r = client.post("/v1/chat/completions",
                            json={"messages": [{"role": "user", "content": "hi"}]},
                            headers=self._headers())
        self.assertEqual(r.status_code, 422)

    def test_message_without_content_skipped(self):
        """Messages missing 'content' key are skipped during redaction (line 129)."""
        r = client.post("/v1/chat/completions",
                        json={"model": "qwen-max", "messages": [
                            {"role": "user"},  # no content
                            {"role": "assistant", "content": "ok"},
                        ]},
                        headers=self._headers())
        self.assertEqual(r.status_code, 200, r.text)

    def test_message_non_string_content_skipped(self):
        """Numeric content is not a str -> skipped (line 129 isinstance check)."""
        r = client.post("/v1/chat/completions",
                        json={"model": "qwen-max", "messages": [
                            {"role": "user", "content": 123},
                            {"role": "assistant", "content": "ok"},
                        ]},
                        headers=self._headers())
        self.assertEqual(r.status_code, 200, r.text)

    def test_pii_fail_closed_raises_503(self):
        """pii_fail_open=False + detector crash -> 503 (line 143)."""
        import app.config as config_mod

        async def _explode(trace_id, text):
            raise RuntimeError("detector crash")

        # Must patch BOTH the source AND app.api.chat's local binding
        with patch("app.pii.redactor.redact", new=_explode):
            with patch("app.api.chat.redact", new=_explode):
                settings = config_mod.get_settings()
                orig = settings.pii_fail_open
                settings.pii_fail_open = False
                try:
                    r = client.post("/v1/chat/completions",
                                    json=self._valid_body(),
                                    headers=self._headers())
                    self.assertEqual(r.status_code, 503, r.text)
                finally:
                    settings.pii_fail_open = orig

    def test_upstream_5xx_returns_502(self):
        """Upstream5xx -> 502 (lines 166-168)."""
        from app.errors import Upstream5xx

        async def _raise(base_url, path, body, headers):
            raise Upstream5xx("5xx")

        with patch("app.api.chat.call_upstream", new=_raise):
            r = client.post("/v1/chat/completions", json=self._valid_body(),
                            headers=self._headers())
        self.assertEqual(r.status_code, 502, r.text)

    def test_upstream_rate_limited_returns_429(self):
        """UpstreamRateLimited -> 429 (lines 169-170)."""
        from app.errors import UpstreamRateLimited

        async def _raise(base_url, path, body, headers):
            raise UpstreamRateLimited("429")

        with patch("app.api.chat.call_upstream", new=_raise):
            r = client.post("/v1/chat/completions", json=self._valid_body(),
                            headers=self._headers())
        self.assertEqual(r.status_code, 429, r.text)

    def test_upstream_generic_exception_returns_502(self):
        """Generic exception -> 502 (lines 171-173)."""
        async def _raise(base_url, path, body, headers):
            raise RuntimeError("unexpected")

        with patch("app.api.chat.call_upstream", new=_raise):
            r = client.post("/v1/chat/completions", json=self._valid_body(),
                            headers=self._headers())
        self.assertEqual(r.status_code, 502, r.text)


if __name__ == "__main__":
    unittest.main()
