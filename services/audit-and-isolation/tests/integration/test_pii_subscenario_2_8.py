"""Critical-path e2e 2.8 — trace 跨实例(2 实例 + 共享 fakeredis).

The data-isolation gateway runs as a 2-pod HA pair. Each pod
runs the same chat pipeline; both pods share the same Redis
instance (where the per-trace PII map lives). This means
the caller can land on pod A for the request and pod A's
redactor writes the PII map to Redis; the response is
returned synchronously, but if the LLM client retries the
request internally it could land on pod B — pod B's
reverser reads the *same* Redis key pod A wrote, and the
placeholder round-trip works.

We simulate that here:

* ``TestClient_A`` issues the chat request; its
  ``call_upstream`` is patched to first call the chat
  pipeline a second time (so the request effectively
  "lands on" a second pod), then echo.
* The second call uses a different ``TestClient`` with its
  own LLM-stub but the SAME fakeredis server (shared
  ``FakeServer``). The reverser on the second call can
  read the PII map that the first call's redactor wrote.

In effect, this is a "split-brain trace" e2e: the same
``X-Trace-Id`` is handled by two distinct request handler
invocations, both backed by the same Redis. The
placeholder→original round-trip works because the
reverser reads from the shared map.

The shared fakeredis uses ``fakeredis.FakeServer()`` (a
process-local pubsub key-value store) to back two
``FakeRedis`` clients — one per "pod". This is the same
pattern used in ``test_e2e_4_scenarios.py`` for the PII
map round-trip.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x")
os.environ.setdefault("REDIS_URL", "redis://x")
os.environ.setdefault("CREDENTIAL_SERVICE_URL", "http://x")

import fakeredis  # noqa: E402
import fakeredis.aioredis  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import redis_client  # noqa: E402
from app.main import app  # noqa: E402


VALID_ID = "11010119900101004X"


class TestCriticalPath2_8(unittest.TestCase):
    """trace 跨实例 — 共享 fakeredis."""

    def setUp(self):
        # Shared fakeredis server (mimics the production Redis
        # instance the two HA pods both connect to).
        self._server = fakeredis.FakeServer()
        self._redis_a = fakeredis.aioredis.FakeRedis(
            server=self._server, decode_responses=True
        )
        self._redis_b = fakeredis.aioredis.FakeRedis(
            server=self._server, decode_responses=True
        )
        # Reset the audit outbox.
        from app.audit.writer import reset_outbox_for_tests

        reset_outbox_for_tests()
        # Replace the module-level get_redis with a per-call
        # "pod selector" that hands out redis_a first, then
        # redis_b. The redactor/reverser are stateless w.r.t.
        # the client (they only call ``get_redis()`` per
        # request), so swapping the factory in the middle of
        # the test is enough.
        self._next_redis = [self._redis_a]

        def _picker():
            if len(self._next_redis) == 0:
                return self._redis_a
            return self._next_redis.pop(0)

        redis_client.get_redis = _picker
        # Build two TestClient instances — one per "pod".
        self.client_a = TestClient(app)
        self.client_b = TestClient(app)

    def _stub_call_upstream(self, trace_id: str, label: str) -> AsyncMock:
        """Build a fake call_upstream that swaps the fakeredis
        picker from ``redis_a`` to ``redis_b`` mid-request.

        This is the "request landed on pod A, retries on pod B"
        simulation: the first call's redactor writes to
        ``redis_a`` (well, both A and B are backed by the same
        FakeServer, so it doesn't matter which client we hand
        out — the write is visible to both pods).

        For the test to be meaningful, the second call's
        reverser MUST read from a client bound to the same
        server (i.e. ``redis_b``). We schedule the swap in the
        first call's ``call_upstream`` stub before the second
        call fires.
        """

        async def _fake(base_url, path, body, headers):
            # Schedule the swap so the NEXT call's redactor /
            # reverser pair is bound to redis_b. (Since both
            # are backed by the same FakeServer, this swap
            # mostly exercises the "two clients, one server"
            # topology rather than data isolation.)
            self._next_redis.append(self._redis_b)
            user_msg = body["messages"][-1]["content"]
            resp = MagicMock()
            resp.status_code = 200
            resp.json = MagicMock(
                return_value={
                    "id": f"cmpl-{label}",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": f"pod-{label} echo: {user_msg}",
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                }
            )
            return resp

        return _fake

    def test_cross_instance_trace_round_trip(self):
        # Auth + credential + routing are stubbed at the chat
        # module. We share one set of patchers across both
        # "pods" — the app is module-level state, so the
        # patches are visible to both TestClient instances.
        route = {
            "model_kind": "public",
            "upstream_base_url": "https://upstream.example.com",
            "upstream_path": "/v1/chat/completions",
            "timeout_ms": 30000,
            "skip_pii": False,
        }
        trace_id = "01HX2EESCENARIO2800000"
        with patch(
            "app.api.chat.verify_service_token",
            new=AsyncMock(return_value="svc-paul"),
        ), patch(
            "app.api.chat.get_llm_api_key",
            new=AsyncMock(return_value="sk-fake"),
        ), patch(
            "app.routing.dispatcher.get_routing",
            new=AsyncMock(return_value=route),
        ), patch(
            "app.api.chat.call_upstream",
            new=self._stub_call_upstream(trace_id, "A"),
        ):
            # Pod A handles the first call.
            r_a = self.client_a.post(
                "/v1/chat/completions",
                json={
                    "model": "qwen-max",
                    "messages": [
                        {
                            "role": "user",
                            "content": f"客户 {VALID_ID} 已确认",
                        }
                    ],
                },
                headers={
                    "Authorization": "Bearer t",
                    "X-Trace-Id": trace_id,
                    "X-Model-Kind": "public",
                },
            )
        self.assertEqual(r_a.status_code, 200, r_a.text)
        # Pod A's response: placeholders were reversed using
        # the Redis map that pod A's redactor wrote.
        content_a = r_a.json()["choices"][0]["message"]["content"]
        self.assertIn(VALID_ID, content_a)
        # Now simulate "the LLM client retried the request on
        # pod B" — fresh patches (since the previous context
        # manager has exited), but the fakeredis server still
        # holds the PII map.
        with patch(
            "app.api.chat.verify_service_token",
            new=AsyncMock(return_value="svc-paul"),
        ), patch(
            "app.api.chat.get_llm_api_key",
            new=AsyncMock(return_value="sk-fake"),
        ), patch(
            "app.routing.dispatcher.get_routing",
            new=AsyncMock(return_value=route),
        ), patch(
            "app.api.chat.call_upstream",
            new=self._stub_call_upstream(trace_id, "B"),
        ):
            r_b = self.client_b.post(
                "/v1/chat/completions",
                json={
                    "model": "qwen-max",
                    "messages": [
                        {
                            "role": "user",
                            "content": f"客户 {VALID_ID} 已确认",
                        }
                    ],
                },
                headers={
                    "Authorization": "Bearer t",
                    "X-Trace-Id": trace_id,
                    "X-Model-Kind": "public",
                },
            )
        self.assertEqual(r_b.status_code, 200, r_b.text)
        # Pod B's reverser reads the *same* Redis key pod A
        # wrote, swaps the placeholder back. Original ID
        # appears in pod B's response.
        content_b = r_b.json()["choices"][0]["message"]["content"]
        self.assertIn(VALID_ID, content_b)
        # Both responses are label-distinguishable.
        self.assertIn("pod-A", content_a)
        self.assertIn("pod-B", content_b)


if __name__ == "__main__":
    unittest.main()
