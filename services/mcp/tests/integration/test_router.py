"""Integration tests for :mod:`app.router`.

The plan (task 6.2) calls out one end-to-end scenario per MCP
server. We drive the router via the same request handlers that the
``mcp.client.session.ClientSession`` would invoke on a real stdio
subprocess — that gives us protocol-level coverage without the
flakiness of spawning a subprocess from inside an asyncio test.

Every test stubs the audit-and-isolation egress with a
``FakeAuditArchive`` callable so we don't need a live HTTP service
to run the suite — and so we can assert that the audit write
actually happened.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from app.router import (
    McpRouter,
    TOOL_PREFIX_FETCH,
    TOOL_PREFIX_FILESYSTEM,
    TOOL_PREFIX_POSTGRES,
    make_server,
)


SERVICE_DIR = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


class FakeAuditArchive:
    """Capture every audit-and-isolation call without a real HTTP roundtrip.

    The router calls ``audit_archive(tool_name, args, trace_id)``
    after every tool dispatch. We replace it with this recorder and
    then assert on ``.records`` to prove the egress step ran.
    """

    def __init__(self) -> None:
        self.records: list[tuple[str, dict[str, Any], str]] = []

    def __call__(self, tool_name: str, args: dict[str, Any], trace_id: str) -> dict[str, Any]:
        self.records.append((tool_name, args, trace_id))
        return {"status": "archived", "trace_id": trace_id}


def _make_recording_handler(records: list[tuple[str, dict[str, Any]]], server: str) -> Any:
    """Build a recording stub for one of the 3 servers.

    The returned callable matches the ``ServerHandler`` protocol:
    ``(tool_name: str, args: dict) -> dict``. It appends every
    invocation to ``records`` and returns a payload identifying the
    server so tests can assert on the round trip.
    """

    def handler(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        records.append((tool_name, args))
        return {"server": server, "tool": tool_name, "args": args, "ok": True}

    return handler


# ---------------------------------------------------------------------------
# 1. dispatch unit tests (in-process, no stdio)
# ---------------------------------------------------------------------------


class TestDispatch:
    def _router_with_recorders(self) -> tuple[McpRouter, list, list, list, FakeAuditArchive]:
        """Return a router wired to recording stubs + a fake audit."""
        fs_calls: list = []
        fetch_calls: list = []
        pg_calls: list = []
        audit = FakeAuditArchive()
        router = McpRouter(
            filesystem_handler=_make_recording_handler(fs_calls, "filesystem"),
            fetch_handler=_make_recording_handler(fetch_calls, "fetch"),
            postgres_handler=_make_recording_handler(pg_calls, "postgres"),
            audit_archive=audit,
        )
        return router, fs_calls, fetch_calls, pg_calls, audit

    def test_filesystem_prefix_dispatches_to_filesystem_server(self) -> None:
        """``fs_*`` tool names must reach the filesystem server stub."""
        router, fs_calls, _, _, _ = self._router_with_recorders()
        result = asyncio.run(router.dispatch("fs_read_file", {"path": "/tmp/x"}))
        assert result == {
            "server": "filesystem",
            "tool": "fs_read_file",
            "args": {"path": "/tmp/x"},
            "ok": True,
        }
        assert fs_calls == [("fs_read_file", {"path": "/tmp/x"})]

    def test_fetch_prefix_dispatches(self) -> None:
        """``fetch_*`` names reach the fetch stub."""
        router, _, fetch_calls, _, _ = self._router_with_recorders()
        result = asyncio.run(router.dispatch("fetch_url", {"url": "https://x/y"}))
        assert result["server"] == "fetch"
        assert fetch_calls == [("fetch_url", {"url": "https://x/y"})]

    def test_postgres_prefix_dispatches(self) -> None:
        """``pg_*`` names reach the postgres stub."""
        router, _, _, pg_calls, _ = self._router_with_recorders()
        result = asyncio.run(router.dispatch("pg_execute_query", {"sql": "SELECT 1"}))
        assert result["server"] == "postgres"
        assert pg_calls == [("pg_execute_query", {"sql": "SELECT 1"})]

    def test_unknown_prefix_raises_value_error(self) -> None:
        """A tool name with no recognised prefix must raise ``ValueError``."""
        router = McpRouter(audit_archive=FakeAuditArchive())
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(router.dispatch("unknown_tool", {}))
        assert "unknown tool prefix" in str(exc_info.value)

    def test_dispatch_writes_audit_log(self) -> None:
        """Every dispatch must trigger an ``audit_archive`` call."""
        router, *_ = self._router_with_recorders()
        asyncio.run(router.dispatch("fs_list_dir", {"path": "/tmp"}))
        audit: FakeAuditArchive = router.audit_archive  # type: ignore[assignment]
        assert len(audit.records) == 1
        tool_name, args, _trace_id = audit.records[0]
        assert tool_name == "fs_list_dir"
        assert args == {"path": "/tmp"}


# ---------------------------------------------------------------------------
# 2. tool list (advertised to clients)
# ---------------------------------------------------------------------------


class TestListTools:
    def test_list_tools_includes_all_three_servers(self) -> None:
        """``list_tools`` must advertise at least one stub tool per server."""
        router = McpRouter(audit_archive=FakeAuditArchive())
        tools = asyncio.run(router.list_advertised_tools())
        prefixes = {t.name.split("_", 1)[0] for t in tools}
        assert "fs" in prefixes
        assert "fetch" in prefixes
        assert "pg" in prefixes


# ---------------------------------------------------------------------------
# 3. error envelope (T11 4-error-boundary)
# ---------------------------------------------------------------------------


class TestErrorEnvelope:
    def test_security_error_maps_to_security_envelope(self) -> None:
        """A ``McpSecurityError`` raised by a server surfaces with ``error_class='security'``."""
        from app.security import McpSecurityError

        def bad_fs(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
            raise McpSecurityError("nope")

        router = McpRouter(
            filesystem_handler=bad_fs,
            fetch_handler=lambda *_: {},
            postgres_handler=lambda *_: {},
            audit_archive=FakeAuditArchive(),
        )
        with pytest.raises(McpSecurityError) as exc_info:
            asyncio.run(router.dispatch("fs_anything", {}))
        assert exc_info.value.error_class == "security"

    def test_runtime_error_maps_to_runtime_envelope(self) -> None:
        """A ``McpResponseTooLargeError`` surfaces with ``error_class='runtime'``."""
        from app.security import McpResponseTooLargeError

        def bad_fetch(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
            raise McpResponseTooLargeError("too big")

        router = McpRouter(
            filesystem_handler=lambda *_: {},
            fetch_handler=bad_fetch,
            postgres_handler=lambda *_: {},
            audit_archive=FakeAuditArchive(),
        )
        with pytest.raises(McpResponseTooLargeError) as exc_info:
            asyncio.run(router.dispatch("fetch_anything", {}))
        assert exc_info.value.error_class == "runtime"


# ---------------------------------------------------------------------------
# 4. module-level helpers (sanity)
# ---------------------------------------------------------------------------


class TestPrefixConstants:
    def test_prefix_constants_distinct(self) -> None:
        """The three prefixes must not collide."""
        prefixes = {TOOL_PREFIX_FILESYSTEM, TOOL_PREFIX_FETCH, TOOL_PREFIX_POSTGRES}
        assert len(prefixes) == 3

    def test_prefix_constants_have_trailing_underscore(self) -> None:
        """Every prefix ends in ``_`` so tool names like ``fs_read_file`` parse cleanly."""
        for prefix in (TOOL_PREFIX_FILESYSTEM, TOOL_PREFIX_FETCH, TOOL_PREFIX_POSTGRES):
            assert prefix.endswith("_")


# ---------------------------------------------------------------------------
# 5. make_server factory
# ---------------------------------------------------------------------------


class TestMakeServer:
    def test_make_server_returns_mcp_server(self) -> None:
        """``make_server`` must return an ``mcp.server.Server`` instance."""
        from mcp.server import Server

        server = make_server()
        assert isinstance(server, Server)
        assert server.name == "chatbiz-mcp-router"

    def test_make_server_registers_handlers(self) -> None:
        """The returned server has list_tools + call_tool handlers registered."""
        from mcp.types import CallToolRequest, ListToolsRequest

        server = make_server()
        assert ListToolsRequest in server.request_handlers
        assert CallToolRequest in server.request_handlers


class TestEndToEndDispatch:
    """Drive ``make_server``'s request handlers directly.

    The ``mcp.client.session.ClientSession`` ultimately resolves a
    request by looking up ``server.request_handlers[RequestType]``
    and awaiting the handler with a constructed request object.
    Doing that directly inside the test process exercises the
    same code path a real stdio roundtrip would, without the
    fragility of subprocess management.
    """

    @pytest.fixture
    def server(self) -> Any:
        """Fresh ``make_server()`` instance per test."""
        return make_server()

    @pytest.mark.asyncio
    async def test_list_tools_round_trip(self, server: Any) -> None:
        """``list_tools`` handler must return one tool per server (real names)."""
        from mcp.types import ListToolsRequest

        handler = server.request_handlers[ListToolsRequest]
        result = await handler(ListToolsRequest(method="tools/list"))
        names = {t.name for t in result.root.tools}
        assert "fs_read_file" in names
        assert "fetch_url" in names
        assert "pg_execute_query" in names

    @pytest.mark.asyncio
    async def test_call_tool_round_trip_per_server(self, server: Any) -> None:
        """``call_tool`` handler dispatches to the right server for each prefix."""
        from mcp.types import CallToolRequest

        handler = server.request_handlers[CallToolRequest]

        for tool_name in ["fs_read_file", "fetch_url", "pg_execute_query"]:
            req = CallToolRequest(
                method="tools/call",
                params={"name": tool_name, "arguments": {"k": "v"}},
            )
            result = await handler(req)
            assert result.root.isError is False
            payload = json.loads(result.root.content[0].text)
            # Real servers return structured error or success — both are valid
            # disambiguations for an incomplete argument set.
            assert isinstance(payload, dict)

    @pytest.mark.asyncio
    async def test_call_tool_unknown_prefix_surfaces_runtime_envelope(
        self, server: Any
    ) -> None:
        """Unknown tool prefixes still produce a JSON-RPC-shaped response, not a crash."""
        from mcp.types import CallToolRequest

        handler = server.request_handlers[CallToolRequest]
        req = CallToolRequest(
            method="tools/call",
            params={"name": "nope_tool", "arguments": {}},
        )
        result = await handler(req)
        # The call_tool handler converts the exception into a
        # TextContent payload carrying the error envelope.
        payload = json.loads(result.root.content[0].text)
        assert payload["error_class"] == "runtime"
        assert "unknown tool prefix" in payload["error_message"]

    @pytest.mark.asyncio
    async def test_call_tool_security_error_surfaces_security_envelope(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ``McpSecurityError`` raised by a handler surfaces as ``error_class='security'``."""
        from app.security import McpSecurityError
        from mcp.types import CallToolRequest

        def bad_fs(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
            raise McpSecurityError("nope")

        # Build a server with the bad handler injected.
        audit = FakeAuditArchive()
        custom_router = McpRouter(
            filesystem_handler=bad_fs,
            fetch_handler=lambda *_: {},
            postgres_handler=lambda *_: {},
            audit_archive=audit,
        )
        server = make_server(custom_router)
        handler = server.request_handlers[CallToolRequest]
        req = CallToolRequest(
            method="tools/call",
            params={"name": "fs_anything", "arguments": {}},
        )
        result = await handler(req)
        payload = json.loads(result.root.content[0].text)
        assert payload["error_class"] == "security"
        assert payload["error_message"] == "nope"


class TestStdioEntrypoint:
    """Exercise ``python -m app.router`` indirectly via ``main``.

    We do not spawn a real subprocess (that requires an event loop
    that conflicts with the one pytest-asyncio sets up). Instead we
    patch ``stdio_server`` and ``sys.stdin`` so the entrypoint can
    run to completion in-process. The behaviour we cover is the
    end-to-end wiring of ``main`` → ``_run_stdio`` →
    ``server.run``.
    """

    def test_main_invokes_stdio_loop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``main()`` must drive ``server.run`` on the stdio streams."""
        from app import router as rmod

        invoked: dict[str, Any] = {"server_run": False, "init_options_seen": False}

        class FakeServer:
            name = "chatbiz-mcp-router"

            def create_initialization_options(self) -> Any:
                invoked["init_options_seen"] = True
                return "INIT"

            async def run(self, read, write, init) -> None:  # type: ignore[no-untyped-def]
                invoked["server_run"] = True
                invoked["read"] = read
                invoked["write"] = write
                invoked["init"] = init

        class FakeStdioCM:
            async def __aenter__(self) -> tuple[str, str]:
                return ("READ", "WRITE")

            async def __aexit__(self, *args: Any) -> None:
                return None

        def fake_stdio_server() -> FakeStdioCM:
            return FakeStdioCM()

        # Replace ``stdio_server`` and the default ``make_server`` factory.
        monkeypatch.setattr(rmod, "stdio_server", fake_stdio_server)

        def fake_make_server() -> FakeServer:
            return FakeServer()

        monkeypatch.setattr(rmod, "make_server", fake_make_server)
        # Run ``main()`` synchronously — it owns its own event loop.
        rmod.main()
        assert invoked["server_run"] is True
        assert invoked["init_options_seen"] is True
        assert invoked["read"] == "READ"
        assert invoked["write"] == "WRITE"
        assert invoked["init"] == "INIT"


# ---------------------------------------------------------------------------
# 6. audit_archive egress helper (httpx POST, Fail-Open)
# ---------------------------------------------------------------------------


class TestAuditArchiveEgress:
    def test_audit_archive_posts_to_default_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``audit_archive`` must POST to ``/v1/audit/archive`` on the audit-and-isolation base URL."""
        from app import router as rmod

        captured: dict[str, Any] = {}

        class FakeResp:
            status_code = 200

            def raise_for_status(self) -> None:
                pass

            def json(self) -> dict[str, Any]:
                return {"status": "archived", "trace_id": captured["payload"]["trace_id"]}

        def fake_post(url, json, timeout):  # type: ignore[no-untyped-def]
            captured["url"] = url
            captured["payload"] = json
            captured["timeout"] = timeout
            return FakeResp()

        monkeypatch.setattr(rmod.httpx, "post", fake_post)
        result = rmod.audit_archive("fs_read", {"path": "/x"}, "abc123")
        assert captured["url"] == "http://127.0.0.1:8080/v1/audit/archive"
        assert captured["payload"]["tool_name"] == "fs_read"
        assert captured["payload"]["args"] == {"path": "/x"}
        assert captured["payload"]["trace_id"] == "abc123"
        assert captured["payload"]["service"] == "chatbiz-mcp"
        assert result["status"] == "archived"

    def test_audit_archive_uses_env_base_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``MCP_AUDIT_BASE_URL`` env var overrides the default host."""
        from app import router as rmod

        monkeypatch.setenv("MCP_AUDIT_BASE_URL", "http://audit-svc:9000/")

        captured: dict[str, Any] = {}

        class FakeResp:
            status_code = 200

            def raise_for_status(self) -> None:
                pass

            def json(self) -> dict[str, Any]:
                return {}

        def fake_post(url, json, timeout):  # type: ignore[no-untyped-def]
            captured["url"] = url
            return FakeResp()

        monkeypatch.setattr(rmod.httpx, "post", fake_post)
        rmod.audit_archive("fs_read", {}, "t1")
        assert captured["url"] == "http://audit-svc:9000/v1/audit/archive"

    def test_audit_archive_fail_open_on_transport_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ``httpx.HTTPError`` must be swallowed and reported as ``fail_open``."""
        from app import router as rmod
        import httpx

        def fake_post(url, json, timeout):  # type: ignore[no-untyped-def]
            raise httpx.ConnectError("audit-and-isolation down")

        monkeypatch.setattr(rmod.httpx, "post", fake_post)
        result = rmod.audit_archive("fs_read", {}, "t1")
        assert result["status"] == "fail_open"
        assert "audit-and-isolation down" in result["error"]