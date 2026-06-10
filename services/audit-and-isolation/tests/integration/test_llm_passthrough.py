"""Integration tests for the LLM pass-through pipeline.

The full pipeline runs in a FastAPI ``TestClient`` and we mock
the upstream with ``respx`` (an ``httpx`` mock library). The test
verifies:

* the request body sent to the upstream is byte-for-byte identical
  to the inbound body (after PII redaction, in the relevant
  scenario)
* the upstream's response status + body are passed through to
  the caller

We don't install ``respx`` (per the "do not install dependencies"
rule). Instead we use the same approach as the unit tests: a
monkey-patched ``httpx.AsyncClient`` that returns canned
``httpx.Response`` objects. The point of the integration test
is to exercise the *call_upstream* function with realistic inputs,
not the FastAPI HTTP layer (the HTTP layer tests come in Phase 10).
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.llm.client import call_upstream, reset_client_for_tests


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _build_response(status_code: int, body: dict) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=body,
        request=httpx.Request("POST", "https://upstream.example.com/v1/chat/completions"),
    )


class TestLLMPassthrough(unittest.TestCase):
    """End-to-end call_upstream behaviour against a mocked upstream."""

    def setUp(self):
        reset_client_for_tests()

    def test_passes_through_full_request_body(self):
        """The full request body (including unknown fields) is
        forwarded to the upstream."""
        body = {
            "model": "qwen-max",
            "messages": [
                {"role": "system", "content": "You are a financial analyst."},
                {"role": "user", "content": "客户 11010119900101004X 想看月报"},
            ],
            "temperature": 0.7,
            "max_tokens": 1024,
            "stream": False,
            "workflow_id": "wf-001",  # unknown to OpenAI schema
        }
        upstream_response = _build_response(
            200,
            {
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "created": 1700000000,
                "model": "qwen-max",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 50,
                    "completion_tokens": 1,
                    "total_tokens": 51,
                },
            },
        )
        client = AsyncMock()
        client.post = AsyncMock(return_value=upstream_response)
        with patch("app.llm.client.get_client", return_value=client):
            resp = _run(
                call_upstream(
                    "https://upstream.example.com",
                    "/v1/chat/completions",
                    body,
                    {"Authorization": "Bearer test-key"},
                )
            )
        # Status + body passed through
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["choices"][0]["message"]["content"], "ok")
        # The full body was forwarded (httpx is what serialises to JSON)
        call_args = client.post.call_args
        forwarded_body = call_args.kwargs.get("json") or call_args.args[1]
        self.assertEqual(forwarded_body, body)
        # And the Authorization header was forwarded
        forwarded_headers = call_args.kwargs.get("headers") or {}
        self.assertEqual(forwarded_headers.get("Authorization"), "Bearer test-key")

    def test_redacted_body_bytewise(self):
        """Simulates the PII redactor's output: the body sent to the
        upstream contains placeholders, not the original PII.

        This test exercises the *contract* the chat pipeline relies
        on — that the redacted body is the one ``call_upstream``
        forwards, byte-for-byte.
        """
        redacted_body = {
            "model": "qwen-max",
            "messages": [
                {
                    "role": "user",
                    "content": "客户 [身份证_04X] 想看月报",  # PII replaced
                }
            ],
            "temperature": 0.7,
            "stream": False,
        }
        upstream_response = _build_response(
            200,
            {
                "id": "x",
                "object": "chat.completion",
                "created": 1,
                "model": "qwen-max",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "[身份证_04X] 是高净值"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            },
        )
        client = AsyncMock()
        client.post = AsyncMock(return_value=upstream_response)
        with patch("app.llm.client.get_client", return_value=client):
            resp = _run(
                call_upstream(
                    "https://upstream.example.com",
                    "/v1/chat/completions",
                    redacted_body,
                    {},
                )
            )
        # The upstream saw the redacted body, not the original PII
        call_args = client.post.call_args
        forwarded = call_args.kwargs.get("json") or call_args.args[1]
        self.assertEqual(forwarded["messages"][0]["content"], "客户 [身份证_04X] 想看月报")
        # The response from the upstream is passed back unchanged
        self.assertIn("[身份证_04X]", resp.text)

    def test_upstream_4xx_passed_through(self):
        body = {"model": "x", "messages": []}
        err = _build_response(400, {"error": {"message": "bad", "type": "x"}})
        client = AsyncMock()
        client.post = AsyncMock(return_value=err)
        with patch("app.llm.client.get_client", return_value=client):
            resp = _run(call_upstream("https://u", "/v1", body, {}))
        self.assertEqual(resp.status_code, 400)
        # Body round-trips
        self.assertEqual(resp.json()["error"]["message"], "bad")

    def test_upstream_5xx_then_200(self):
        body = {"model": "x", "messages": [{"role": "user", "content": "hi"}]}
        err5xx = _build_response(503, {"error": "unavailable"})
        ok = _build_response(200, {"ok": True})
        client = AsyncMock()
        client.post = AsyncMock(side_effect=[err5xx, ok])
        with patch("app.llm.client.get_client", return_value=client):
            resp = _run(call_upstream("https://u", "/v1", body, {}))
        self.assertEqual(resp.status_code, 200)
        # Body and post count reflect the retry
        self.assertEqual(client.post.await_count, 2)


if __name__ == "__main__":
    unittest.main()
