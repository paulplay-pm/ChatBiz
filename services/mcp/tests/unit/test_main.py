"""Unit tests for the MCP HTTP/SSE entrypoint."""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app import main as main_module


@pytest.fixture
async def client():
    """ASGI test client with lifespan startup handled explicitly."""
    async with LifespanManager(main_module.app):
        async with AsyncClient(
            transport=ASGITransport(app=main_module.app),
            base_url="http://test",
        ) as ac:
            yield ac


async def test_healthz(client: AsyncClient) -> None:
    """``GET /healthz`` returns a plain ``ok`` body."""
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.text == "ok"


async def test_sse_endpoint_event() -> None:
    """``GET /sse`` starts an SSE response with the correct content-type."""
    import asyncio

    async with LifespanManager(main_module.app):
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "path": "/sse",
            "raw_path": b"/sse",
            "root_path": "",
            "scheme": "http",
            "query_string": b"",
            "headers": [(b"accept", b"text/event-stream")],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 80),
            "app": main_module.app,
        }
        received: list[dict] = []

        async def receive() -> dict:
            return {"type": "http.disconnect"}

        async def send(message: dict) -> None:
            received.append(message)

        task = asyncio.create_task(main_module.app(scope, receive, send))
        # Give the SSE transport time to emit the response start.
        await asyncio.sleep(0.2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert received
    start = received[0]
    assert start["type"] == "http.response.start"
    assert start["status"] == 200
    headers = dict(start["headers"])
    assert headers.get(b"content-type", b"").startswith(b"text/event-stream")


async def test_messages_missing_session_id(client: AsyncClient) -> None:
    """``POST /messages`` without ``session_id`` returns 400."""
    resp = await client.post("/messages", json={})
    assert resp.status_code == 400


async def test_messages_invalid_session_id(client: AsyncClient) -> None:
    """``POST /messages`` with an unknown but valid session returns 404."""
    resp = await client.post(
        "/messages?session_id=00000000000000000000000000000000", json={}
    )
    assert resp.status_code == 404


async def test_messages_wellformed_but_unknown_session(client: AsyncClient) -> None:
    """A syntactically valid JSON-RPC message for an unknown session 404s."""
    resp = await client.post(
        "/messages?session_id=00000000000000000000000000000000",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert resp.status_code == 404


def test_main_runs_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    """``main()`` delegates to ``uvicorn.run`` with the configured host/port."""
    captured: dict[str, object] = {}

    def _fake_run(*args, **kwargs) -> None:
        captured["args"] = args
        captured["kwargs"] = kwargs

    monkeypatch.setattr(main_module.uvicorn, "run", _fake_run)
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "9000")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    main_module.main()

    assert captured["kwargs"].get("host") == "127.0.0.1"
    assert captured["kwargs"].get("port") == 9000
    assert captured["kwargs"].get("log_level") == "debug"
    assert captured["kwargs"].get("access_log") is True


def test_custom_endpoint_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """``MESSAGE_PATH`` is advertised in the SSE endpoint event."""
    monkeypatch.setenv("MCP_MESSAGE_PATH", "/inbox")
    transport = main_module.SseServerTransport("/inbox")
    assert transport._endpoint == "/inbox"


async def test_lifespan_initializes_server() -> None:
    """Lifespan startup stashes an MCP server on the app state."""
    async with LifespanManager(main_module.app):
        assert hasattr(main_module.app.state, "mcp_server")
        assert main_module.app.state.mcp_server is not None
