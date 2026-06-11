"""Unit tests for app/clients/knowledge_base.py — stub 503 behavior."""
import pytest
import respx
from httpx import Response
from app.clients.knowledge_base import KnowledgeBaseClient
from app.errors.classes import WorkflowRuntimeError


@pytest.mark.asyncio
@respx.mock
async def test_retrieve_returns_json_on_200():
    respx.post("http://knowledge-base-test:8002/retrieve").mock(
        return_value=Response(200, json={"chunks": [{"text": "hello", "score": 0.9}]})
    )
    c = KnowledgeBaseClient()
    try:
        r = await c.retrieve("kb-1", "query", 5)
        assert r["chunks"][0]["text"] == "hello"
    finally:
        await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_retrieve_503_raises_workflow_runtime_error():
    respx.post("http://knowledge-base-test:8002/retrieve").mock(return_value=Response(503))
    c = KnowledgeBaseClient()
    try:
        with pytest.raises(WorkflowRuntimeError, match="knowledge-base service 未实现"):
            await c.retrieve("kb-1", "query", 5)
    finally:
        await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_retrieve_propagates_kwargs():
    captured = {}

    def cb(request):
        import json
        captured.update(json.loads(request.content.decode()))
        return Response(200, json={"chunks": []})

    respx.post("http://knowledge-base-test:8002/retrieve").mock(side_effect=cb)
    c = KnowledgeBaseClient()
    try:
        await c.retrieve("kb-99", "hello world", 7)
    finally:
        await c.aclose()
    assert captured["knowledge_base_id"] == "kb-99"
    assert captured["query"] == "hello world"
    assert captured["top_k"] == 7
