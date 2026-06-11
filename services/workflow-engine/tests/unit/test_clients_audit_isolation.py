"""Unit tests for app/clients/audit_isolation.py — respx mock httpx."""
import pytest
import respx
from httpx import Response
from app.clients.audit_isolation import AuditIsolationClient


@pytest.mark.asyncio
@respx.mock
async def test_chat_returns_choices():
    respx.post("http://audit-and-isolation-test:8080/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [{"message": {"content": "hi"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )
    )
    c = AuditIsolationClient()
    try:
        r = await c.chat("gpt-4", [{"role": "user", "content": "hi"}])
        assert r["choices"][0]["message"]["content"] == "hi"
        assert r["usage"]["total_tokens"] == 2
    finally:
        await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_chat_propagates_kwargs():
    """Extra kwargs (temperature, max_tokens) are sent in request body."""
    captured = {}

    def callback(request):
        import json
        body = json.loads(request.content.decode())
        captured.update(body)
        return Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    respx.post("http://audit-and-isolation-test:8080/v1/chat/completions").mock(side_effect=callback)
    c = AuditIsolationClient()
    try:
        await c.chat(
            "gpt-4",
            [{"role": "user", "content": "x"}],
            temperature=0.3,
            max_tokens=1234,
        )
    finally:
        await c.aclose()
    assert captured["model"] == "gpt-4"
    assert captured["temperature"] == 0.3
    assert captured["max_tokens"] == 1234
    assert captured["messages"] == [{"role": "user", "content": "x"}]


@pytest.mark.asyncio
@respx.mock
async def test_chat_raises_on_500():
    respx.post("http://audit-and-isolation-test:8080/v1/chat/completions").mock(return_value=Response(500))
    c = AuditIsolationClient()
    try:
        with pytest.raises(Exception):  # HTTPStatusError
            await c.chat("gpt-4", [{"role": "user", "content": "x"}])
    finally:
        await c.aclose()
