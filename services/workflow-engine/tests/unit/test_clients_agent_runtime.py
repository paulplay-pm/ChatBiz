"""Unit tests for app/clients/agent_runtime.py — stub 503 behavior."""
import pytest
import respx
from httpx import Response
from app.clients.agent_runtime import AgentRuntimeClient
from app.errors.classes import WorkflowRuntimeError


@pytest.mark.asyncio
@respx.mock
async def test_invoke_returns_json_on_200():
    respx.post("http://agent-runtime-test:8003/invoke").mock(
        return_value=Response(200, json={"result": "done", "iterations": 3})
    )
    c = AgentRuntimeClient()
    try:
        r = await c.invoke("agent-1", "do thing", max_iterations=5)
        assert r["result"] == "done"
        assert r["iterations"] == 3
    finally:
        await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_invoke_503_raises_workflow_runtime_error():
    respx.post("http://agent-runtime-test:8003/invoke").mock(return_value=Response(503))
    c = AgentRuntimeClient()
    try:
        with pytest.raises(WorkflowRuntimeError, match="agent-runtime service 未实现"):
            await c.invoke("agent-1", "task")
    finally:
        await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_invoke_propagates_kwargs():
    captured = {}

    def cb(request):
        import json
        captured.update(json.loads(request.content.decode()))
        return Response(200, json={"result": "ok"})

    respx.post("http://agent-runtime-test:8003/invoke").mock(side_effect=cb)
    c = AgentRuntimeClient()
    try:
        await c.invoke("agent-99", "do something", max_iterations=10, tools=["search", "calc"])
    finally:
        await c.aclose()
    assert captured["agent_id"] == "agent-99"
    assert captured["task"] == "do something"
    assert captured["max_iterations"] == 10
    assert captured["tools"] == ["search", "calc"]
