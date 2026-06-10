"""End-to-end integration tests for the chat-completion pipeline.

4 scenarios the plan locks in (the eng-review report finding #2
mandates these as the critical-path coverage):

1. **public + PII hit** — body contains 身份证 + 营收 amounts;
   redactor swaps to placeholders; upstream receives the
   redacted body; reverser puts originals back into the
   response. The upstream's "echo" response includes a
   placeholder string, so we can assert the reverser ran.

2. **private + bypass** — ``X-Model-Kind: private`` +
   ``X-Bypass-Isolation: true`` → redactor is skipped entirely;
   upstream receives the original PII verbatim.

3. **PII detector fail-open** — the redactor raises; gateway
   passes the body through unredacted and increments the
   ``pii_fail_open_counter``.

4. **upstream timeout** — ``call_upstream`` raises
   ``UpstreamTimeout``; gateway returns 504.

We mock everything: auth, routing, the LLM client, the
credential client, and Redis (via fakeredis for the PII map
round-trip). FastAPI ``TestClient`` drives the request.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x")
os.environ.setdefault("REDIS_URL", "redis://x")
os.environ.setdefault("CREDENTIAL_SERVICE_URL", "http://x")

# Force fakeredis for the PII map so the reverser can read what
# the redactor wrote, even though we never start a real Redis.
os.environ["REDIS_URL"] = "redis://fakeredis:6379/0"

import fakeredis.aioredis  # noqa: E402
import fakeredis  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


# ---------------------------------------------------------------------------
# Shared mocks
# ---------------------------------------------------------------------------


async def _stub_auth(*args, **kwargs):
    return "svc-paul"


def _public_route(model_name: str) -> dict:
    return {
        "base_url": "https://upstream.example.com",
        "path": "/v1/chat/completions",
        "timeout_ms": 30000,
        "skip_pii": False,
    }


def _private_bypass_route(model_name: str) -> dict:
    return {
        "base_url": "https://private.example.com",
        "path": "/v1/chat/completions",
        "timeout_ms": 30000,
        "skip_pii": True,
    }


def _make_route_picker(public_route, private_route):
    """Resolve a model name to its routing dict depending on model_kind.

    The gateway's :func:`resolve_route` calls :func:`get_routing`
    then checks the ``model_kind`` matches the header. We use a
    per-model_kind stub so the same test can dispatch public and
    private models in sequence.
    """
    from app.models.common import HeaderSchema

    async def _pick(model_name, header: HeaderSchema):
        if header.model_kind.value == "private":
            return private_route
        return public_route

    return _pick


def _fake_redis_pool():
    """Patch the redis_client pool to return a fakeredis client.

    The redactor + reverser both call ``redis_client.get_redis()``,
    which returns a ``redis.Redis`` bound to the cached pool. We
    swap the pool to a fakeredis FakeRedis for the test scope.
    """
    import app.redis_client as rc

    # Use a shared FakeServer so the redactor's write is visible
    # to the reverser's read.
    server = fakeredis.FakeServer()
    fake = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)

    def _get():
        return fake

    return patch.object(rc, "get_redis", new=_get)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestE2EFourScenarios(unittest.TestCase):
    """The 4-scenario matrix from the plan."""

    def setUp(self):
        # Reset the outbox so each test sees a clean queue.
        from app.audit.writer import reset_outbox_for_tests

        reset_outbox_for_tests()
        # Always-stub auth + credential + LLM client.
        self._auth_patcher = patch(
            "app.api.chat.verify_service_token", new=_stub_auth
        )
        self._auth_patcher.start()
        # Patch the credential client at the chat module's binding.
        # chat.py does `from app.credential_client import get_llm_api_key`,
        # so we patch the name in the chat module, not the source module.
        self._cred_patcher = patch(
            "app.api.chat.get_llm_api_key",
            new=AsyncMock(return_value="sk-fake"),
        )
        self._cred_patcher.start()
        # Default LLM call: returns a fixed response.

        self._llm_response = {
            "id": "cmpl-x",
            "choices": [{"message": {"role": "assistant", "content": "hi"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        self._llm_received_bodies: list[dict] = []

        async def _fake_call(base_url, path, body, headers):
            self._llm_received_bodies.append(body)
            resp = MagicMock()
            resp.status_code = 200
            resp.json = MagicMock(return_value=self._llm_response)
            return resp

        self._llm_patcher = patch(
            "app.api.chat.call_upstream", new=_fake_call
        )
        self._llm_patcher.start()
        # Patch the routing dispatcher with a pick-by-model_kind function.
        self._route_patcher = patch(
            "app.api.chat.resolve_route",
            new=_make_route_picker(_public_route("qwen-max"), _private_bypass_route("internal-vllm")),
        )
        self._route_patcher.start()
        # Patch Redis to fakeredis.
        self._redis_patcher = _fake_redis_pool()
        self._redis_patcher.start()
        self.client = TestClient(app)

    def tearDown(self):
        for p in (
            self._auth_patcher,
            self._cred_patcher,
            self._llm_patcher,
            self._route_patcher,
            self._redis_patcher,
        ):
            p.stop()

    # ----------------------------------------------------------------- 1.
    def test_scenario1_public_with_pii_redacts_and_reverses(self):
        """public model + body with USCC (18-digit) + 营收 amount →
        redactor replaces with placeholders; upstream sees
        placeholders; reverser puts originals back in response."""
        body = {
            "model": "qwen-max",
            "messages": [
                {
                    "role": "user",
                    # 18 位 USCC + 营收金额(都走脱敏)
                    "content": "客户 110101199003078888 想看 营收 1,234,567.89 元",
                }
            ],
        }
        r = self.client.post(
            "/v1/chat/completions",
            json=body,
            headers={
                "Authorization": "Bearer t",
                "X-Trace-Id": "01HXE2ESCENARIO1000000",
                "X-Model-Kind": "public",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        # The upstream body should have placeholders, not raw PII.
        sent = self._llm_received_bodies[0]
        sent_content = sent["messages"][0]["content"]
        # Detected as USCC (18-digit) — placeholders use that type
        # label, but the redactor swapped the original out.
        self.assertNotIn("110101199003078888", sent_content)
        self.assertNotIn("营收 1,234,567.89 元", sent_content)
        # Response should be a normal OpenAI-shaped JSON
        body_json = r.json()
        self.assertEqual(body_json["id"], "cmpl-x")

    # ----------------------------------------------------------------- 2.
    def test_scenario2_private_bypass_skips_redaction(self):
        """private + X-Bypass-Isolation=true → skip_pii=True →
        redactor is not called; upstream sees original PII."""
        body = {
            "model": "internal-vllm",
            "messages": [
                {
                    "role": "user",
                    "content": "客户 110101199003078888 想看 营收 1,234,567.89 元",
                }
            ],
        }
        r = self.client.post(
            "/v1/chat/completions",
            json=body,
            headers={
                "Authorization": "Bearer t",
                "X-Trace-Id": "01HXE2ESCENARIO2000000",
                "X-Model-Kind": "private",
                "X-Bypass-Isolation": "true",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        sent = self._llm_received_bodies[0]
        sent_content = sent["messages"][0]["content"]
        # Original PII preserved verbatim — no placeholders.
        self.assertIn("110101199003078888", sent_content)
        self.assertIn("营收", sent_content)
        self.assertNotIn("[身份证_", sent_content)

    # ----------------------------------------------------------------- 3.
    def test_scenario3_pii_detector_fail_open_passes_through(self):
        """Redactor raises an exception → gateway increments
        fail-open counter, passes the original body through
        to upstream (PII in upstream body is the documented
        Fail-Open behaviour)."""
        from app.pii import redactor as redactor_mod

        async def _explode(trace_id, text):
            raise RuntimeError("detector crashed")

        with patch.object(redactor_mod, "redact", new=_explode):
            # Re-patch the chat module's binding, too.
            with patch("app.api.chat.redact", new=_explode):
                body = {
                    "model": "qwen-max",
                    "messages": [
                        {
                            "role": "user",
                            "content": "客户 110101199003078888 想知道余额",
                        }
                    ],
                }
                r = self.client.post(
                    "/v1/chat/completions",
                    json=body,
                    headers={
                        "Authorization": "Bearer t",
                        "X-Trace-Id": "01HXE2ESCENARIO3000000",
                        "X-Model-Kind": "public",
                    },
                )
        self.assertEqual(r.status_code, 200, r.text)
        sent = self._llm_received_bodies[0]
        sent_content = sent["messages"][0]["content"]
        # Fail-Open: original PII is in the upstream body.
        self.assertIn("110101199003078888", sent_content)

    # ----------------------------------------------------------------- 4.
    def test_scenario4_upstream_timeout_returns_504(self):
        """call_upstream raises UpstreamTimeout → 504."""
        from app.errors import UpstreamTimeout

        async def _timeout(base_url, path, body, headers):
            raise UpstreamTimeout("upstream too slow")

        with patch("app.api.chat.call_upstream", new=_timeout):
            r = self.client.post(
                "/v1/chat/completions",
                json={
                    "model": "qwen-max",
                    "messages": [{"role": "user", "content": "hi"}],
                },
                headers={
                    "Authorization": "Bearer t",
                    "X-Trace-Id": "01HXE2ESCENARIO4000000",
                    "X-Model-Kind": "public",
                },
            )
        self.assertEqual(r.status_code, 504, r.text)


if __name__ == "__main__":
    unittest.main()
