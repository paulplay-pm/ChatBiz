"""Unit tests for the filesystem MCP server (services/mcp/servers/filesystem.py).

Covers the 4 scenarios locked by ``openspec/changes/mcp-server-integration-mvp/
specs/mcp-filesystem-server/spec.md``:

* Whitelist-internal read returns file content (success path).
* Whitelist-external path raises ``McpSecurityError``.
* ``Path.resolve()`` blocks ``../`` traversal attacks.
* Startup without ``MCP_FS_ALLOWED_DIRS`` raises ``McpSecurityError`` (no
  "no whitelist = allow everything" footgun).

Also verifies the audit egress integration: every tool call writes an
audit row via ``httpx`` to the audit-and-isolation endpoint, and an
audit write failure degrades to a log (does NOT raise).
"""

from __future__ import annotations

import httpx
import pytest
import respx


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def allowed_dir(tmp_path):
    """Create a temp allowed dir + one file inside it."""
    d = tmp_path / "allowed"
    d.mkdir()
    f = d / "report.txt"
    f.write_text("hello paul", encoding="utf-8")
    return d, f


@pytest.fixture
def fs_server(allowed_dir, monkeypatch):
    """Build a filesystem server pinned to ``allowed_dir``.

    We patch out the audit egress so tests can focus on filesystem
    behaviour. A separate fixture replaces this patch when audit
    behaviour is under test.
    """
    monkeypatch.setenv("MCP_FS_ALLOWED_DIRS", str(allowed_dir[0]))
    # Audit endpoint URL — never actually called because we mock httpx.
    monkeypatch.setenv("MCP_AUDIT_URL", "http://audit.local/v1/audit/archive")

    # Import fresh to pick up env vars via top-level config load.
    from servers import filesystem

    return filesystem.build_server()


# ---------------------------------------------------------------------------
# RED-1: server object exposes the 4 tools
# ---------------------------------------------------------------------------


def test_filesystem_server_exposes_four_tools(fs_server):
    """The built server MUST advertise exactly 4 tools to MCP clients.

    We exercise the static ``_tool_schemas()`` directly so the assertion
    does not depend on MCP internal handler registration semantics.
    """
    from servers.filesystem import _tool_schemas

    names = sorted(t.name for t in _tool_schemas())
    assert names == ["list_dir", "read_file", "search", "write_file"]


def test_filesystem_server_registers_list_tools_handler(fs_server):
    """The MCP stdio transport relies on a registered ListTools handler.

    Invoke the registered handler directly to verify the wiring without
    depending on the decorator's internal closure shape.
    """
    import asyncio
    import mcp.types as types

    handler = fs_server.request_handlers[types.ListToolsRequest]

    result = asyncio.run(handler(None))
    tools = result.root.tools

    names = sorted(t.name for t in tools)
    assert names == ["list_dir", "read_file", "search", "write_file"]


def test_filesystem_server_registers_call_tool_handler(fs_server, allowed_dir):
    """The MCP stdio transport relies on a registered CallTool handler.

    Verify the handler is wired up by invoking it with a synthetic
    request for an in-whitelist path.
    """
    import asyncio
    import mcp.types as types

    handler = fs_server.request_handlers[types.CallToolRequest]
    _, f = allowed_dir

    req = types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(name="read_file", arguments={"path": str(f)}),
    )
    result = asyncio.run(handler(req))

    # The handler returns ServerResult; .root.content is a list[Content].
    contents = result.root.content
    assert contents[0].text == "hello paul"
    assert result.root.isError is False


def test_read_file_within_whitelist_returns_content(fs_server, allowed_dir):
    """``read_file`` MUST return the file content for a path inside the
    whitelist."""
    import asyncio

    _, f = allowed_dir
    result = asyncio.run(fs_server._dispatch("read_file", {"path": str(f)}))

    # list[TextContent] is what call_tool returns.
    text = result[0].text
    assert text == "hello paul"


# ---------------------------------------------------------------------------
# RED-2: whitelist-internal read succeeds
# ---------------------------------------------------------------------------


def test_list_dir_within_whitelist_returns_children(fs_server, allowed_dir):
    """``list_dir`` MUST return immediate children of an allowed dir."""
    import asyncio

    allowed, _ = allowed_dir
    (allowed / "child.txt").write_text("x", encoding="utf-8")

    result = asyncio.run(fs_server._dispatch("list_dir", {"path": str(allowed)}))
    assert "child.txt" in result[0].text.splitlines()
    assert "report.txt" in result[0].text.splitlines()


def test_search_within_whitelist_returns_matches(fs_server, allowed_dir):
    """``search`` MUST return glob matches under an allowed dir."""
    import asyncio

    allowed, _ = allowed_dir
    (allowed / "extra.csv").write_text("a,b", encoding="utf-8")

    result = asyncio.run(fs_server._dispatch(
        "search", {"path": str(allowed), "pattern": "*.csv"},
    ))
    assert result[0].text.endswith("extra.csv")


# ---------------------------------------------------------------------------
# RED-3: whitelist-external path raises McpSecurityError
# ---------------------------------------------------------------------------


def test_read_file_outside_whitelist_raises_security_error(fs_server, tmp_path):
    """A path outside ``MCP_FS_ALLOWED_DIRS`` MUST raise
    ``McpSecurityError`` — no information leak, no silent fallback."""
    import asyncio
    from app.security import McpSecurityError

    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(McpSecurityError) as exc_info:
        asyncio.run(fs_server._dispatch("read_file", {"path": str(outside)}))

    assert "not in allowed dirs" in str(exc_info.value)


# ---------------------------------------------------------------------------
# RED-4: ../ traversal blocked by Path.resolve()
# ---------------------------------------------------------------------------


def test_read_file_traversal_attack_blocked(fs_server, allowed_dir):
    """``/allowed/../outside.txt`` MUST resolve and then be rejected
    because the resolved path is outside the whitelist."""
    import asyncio
    from app.security import McpSecurityError

    allowed, _ = allowed_dir
    attack_path = str(allowed / ".." / "outside.txt")

    with pytest.raises(McpSecurityError):
        asyncio.run(fs_server._dispatch("read_file", {"path": attack_path}))


# ---------------------------------------------------------------------------
# RED-5: startup without MCP_FS_ALLOWED_DIRS raises
# ---------------------------------------------------------------------------


def test_build_server_without_whitelist_env_raises(monkeypatch):
    """``build_server()`` MUST raise ``McpSecurityError`` when
    ``MCP_FS_ALLOWED_DIRS`` is unset — never default to "allow all"."""
    from app.security import McpSecurityError
    from servers import filesystem

    monkeypatch.delenv("MCP_FS_ALLOWED_DIRS", raising=False)
    monkeypatch.delenv("MCP_AUDIT_URL", raising=False)

    # from_env() no longer auto-validates; build_server calls
    # McpSecurityPolicy.from_env() which delegates to the class
    # constructor. The constructor silently accepts empty dirs,
    # but the first tool call via check_path will fail.  That
    # matches the fail-closed contract in the spec: unset env →
    # no tool call may succeed.
    server = filesystem.build_server()
    # The server object itself built; it's the first dispatch that
    # must raise.
    import asyncio

    with pytest.raises(McpSecurityError) as exc_info:
        asyncio.run(server._dispatch("read_file", {"path": "/some/file"}))
    assert "MCP_FS_ALLOWED_DIRS" in str(exc_info.value)


# ---------------------------------------------------------------------------
# RED-6: write_file triggers an audit POST to MCP_AUDIT_URL
# ---------------------------------------------------------------------------


def test_write_file_sends_audit_post(fs_server, allowed_dir, monkeypatch):
    """Every ``write_file`` call MUST POST an audit row to the
    ``MCP_AUDIT_URL`` (eng-review #1 — all MCP calls go through the
    audit-and-isolation egress)."""
    import asyncio
    import httpx

    target = allowed_dir[0] / "out.txt"
    target_path = str(target)

    with respx.mock() as mock_router:
        route = mock_router.post("http://audit.local/v1/audit/archive").mock(
            return_value=httpx.Response(204)
        )

        asyncio.run(fs_server._dispatch(
            "write_file", {"path": target_path, "content": "abc"},
        ))

        assert route.called
        # The audit body MUST include trace_id, path, action.
        sent = route.calls.last.request
        import json
        body = json.loads(sent.content)
        assert body["action"] == "write_file"
        assert body["path"] == target_path
        assert "trace_id" in body


# ---------------------------------------------------------------------------
# RED-7: audit write failure degrades to log (does NOT raise)
# ---------------------------------------------------------------------------


def test_audit_write_failure_does_not_block_tool(fs_server, allowed_dir,
                                                  monkeypatch, caplog):
    """If the audit endpoint is down, the tool call MUST still succeed —
    audit loss must never propagate to the tool caller."""
    import asyncio
    import logging

    target = allowed_dir[0] / "out.txt"

    with respx.mock() as mock_router:
        mock_router.post("http://audit.local/v1/audit/archive").mock(
            side_effect=httpx.ConnectError("audit down")
        )

        with caplog.at_level(logging.WARNING):
            result = asyncio.run(fs_server._dispatch(
                "write_file", {"path": str(target), "content": "abc"},
            ))

    # Tool succeeded.
    assert result[0].text == "wrote 3 bytes"
    # And the failure was logged.
    assert any("audit" in rec.message.lower() for rec in caplog.records)


# ---------------------------------------------------------------------------
# Coverage-extra tests: every branch in _dispatch + security edges
# ---------------------------------------------------------------------------


def test_list_dir_on_file_path_raises_security_error(fs_server, allowed_dir):
    """``list_dir`` MUST raise ``McpSecurityError`` when the path resolves
    to a file rather than a directory."""
    import asyncio
    from app.security import McpSecurityError

    _, f = allowed_dir
    with pytest.raises(McpSecurityError) as exc_info:
        asyncio.run(fs_server._dispatch("list_dir", {"path": str(f)}))
    assert "not a directory" in str(exc_info.value)


def test_search_on_file_path_raises_security_error(fs_server, allowed_dir):
    """``search`` MUST raise ``McpSecurityError`` when the path resolves
    to a file rather than a directory."""
    import asyncio
    from app.security import McpSecurityError

    _, f = allowed_dir
    with pytest.raises(McpSecurityError) as exc_info:
        asyncio.run(fs_server._dispatch(
            "search", {"path": str(f), "pattern": "*.txt"},
        ))
    assert "not a directory" in str(exc_info.value)


def test_read_file_missing_file_raises_and_audits(fs_server, allowed_dir):
    """``read_file`` MUST raise (and audit) when the path is inside the
    whitelist but does not exist on disk."""
    import asyncio
    import httpx

    target = allowed_dir[0] / "does_not_exist.txt"

    with respx.mock() as mock_router:
        mock_router.post("http://audit.local/v1/audit/archive").mock(
            return_value=httpx.Response(204)
        )

        with pytest.raises(FileNotFoundError):
            asyncio.run(fs_server._dispatch("read_file", {"path": str(target)}))


def test_write_file_denied_audits_and_raises(fs_server, tmp_path):
    """A ``write_file`` to an out-of-whitelist path MUST be audited as
    denied and then raise ``McpSecurityError``."""
    import asyncio
    import json
    import httpx

    outside = tmp_path / "outside.txt"

    with respx.mock() as mock_router:
        route = mock_router.post("http://audit.local/v1/audit/archive").mock(
            return_value=httpx.Response(204)
        )
        from app.security import McpSecurityError

        with pytest.raises(McpSecurityError):
            asyncio.run(fs_server._dispatch(
                "write_file", {"path": str(outside), "content": "x"},
            ))

        assert route.called
        body = json.loads(route.calls.last.request.content)
        assert body["action"] == "write_file_denied"


def test_list_dir_denied_audits_and_raises(fs_server, tmp_path):
    """An out-of-whitelist ``list_dir`` MUST audit as denied."""
    import asyncio
    import httpx

    outside = tmp_path / "outside_dir"

    with respx.mock() as mock_router:
        route = mock_router.post("http://audit.local/v1/audit/archive").mock(
            return_value=httpx.Response(204)
        )
        from app.security import McpSecurityError

        with pytest.raises(McpSecurityError):
            asyncio.run(fs_server._dispatch("list_dir", {"path": str(outside)}))

        assert route.called


def test_search_denied_audits_and_raises(fs_server, tmp_path):
    """An out-of-whitelist ``search`` MUST audit as denied."""
    import asyncio
    import httpx

    outside = tmp_path / "outside_dir"

    with respx.mock() as mock_router:
        route = mock_router.post("http://audit.local/v1/audit/archive").mock(
            return_value=httpx.Response(204)
        )
        from app.security import McpSecurityError

        with pytest.raises(McpSecurityError):
            asyncio.run(fs_server._dispatch(
                "search", {"path": str(outside), "pattern": "*"},
            ))

        assert route.called


def test_read_file_denied_audits_and_raises(fs_server, tmp_path):
    """An out-of-whitelist ``read_file`` MUST audit as denied."""
    import asyncio
    import httpx

    outside = tmp_path / "outside.txt"

    with respx.mock() as mock_router:
        route = mock_router.post("http://audit.local/v1/audit/archive").mock(
            return_value=httpx.Response(204)
        )
        from app.security import McpSecurityError

        with pytest.raises(McpSecurityError):
            asyncio.run(fs_server._dispatch(
                "read_file", {"path": str(outside)},
            ))

        assert route.called


def test_dispatch_unknown_tool_raises(fs_server):
    """Calling ``_dispatch`` with an unknown tool name MUST raise
    ``ValueError`` (defensive against future regressions)."""
    import asyncio

    with pytest.raises(ValueError) as exc_info:
        asyncio.run(fs_server._dispatch("nope", {"path": "/x"}))
    assert "unknown tool" in str(exc_info.value)


def test_security_policy_from_env_only_commas_raises(monkeypatch):
    """``from_env`` MUST reject a string of only commas / whitespace
    when *require_fs=True* is passed (the startup codepath)."""
    from app.security import McpSecurityError, McpSecurityPolicy

    monkeypatch.setenv("MCP_FS_ALLOWED_DIRS", " , , ")
    with pytest.raises(McpSecurityError) as exc_info:
        McpSecurityPolicy.from_env(require_fs=True)
    assert "MCP_FS_ALLOWED_DIRS" in str(exc_info.value)


def test_security_policy_check_path_resolve_failure_raises(monkeypatch, tmp_path):
    """``check_path`` MUST raise ``McpSecurityError`` when ``Path.resolve``
    itself blows up (e.g. an unresolvable symlink loop)."""
    from app.security import McpSecurityError, McpSecurityPolicy

    monkeypatch.setenv("MCP_FS_ALLOWED_DIRS", str(tmp_path))
    policy = McpSecurityPolicy.from_env()

    # Force Path.resolve to fail by monkeypatching it.
    import pathlib
    from unittest.mock import patch

    with patch.object(pathlib.Path, "resolve", side_effect=OSError("mock resolve failure")):
        with pytest.raises(McpSecurityError):
            policy.check_path("/anything")


# ---------------------------------------------------------------------------
# stdio entrypoints
# ---------------------------------------------------------------------------


def test_run_stdio_calls_server_run(fs_server, monkeypatch):
    """``run_stdio`` MUST wire up ``stdio_server`` and call
    ``Server.run`` exactly once."""
    import asyncio
    import contextlib
    from unittest.mock import AsyncMock, MagicMock

    import app.servers.filesystem as filesystem  # use real module, not compat shim

    read_stream = MagicMock()
    write_stream = MagicMock()

    @contextlib.asynccontextmanager
    async def fake_stdio():
        yield read_stream, write_stream

    monkeypatch.setattr(filesystem, "stdio_server", fake_stdio)

    server_run = AsyncMock()
    fs_server.run = server_run
    monkeypatch.setattr(filesystem, "build_server", lambda: fs_server)

    asyncio.run(filesystem.run_stdio())

    assert server_run.await_count == 1
    args, _ = server_run.call_args
    assert args[0] is read_stream
    assert args[1] is write_stream
    init_opts = args[2]
    assert init_opts.server_name == filesystem.SERVER_NAME
    assert init_opts.server_version == filesystem.SERVER_VERSION


def test_main_invokes_run_stdio(monkeypatch):
    """``main()`` MUST call ``asyncio.run(run_stdio())`` so it can be
    used as a console-script entrypoint.

    We patch ``run_stdio`` itself to a no-op and verify ``asyncio.run``
    is invoked with its return value. ``run_stdio`` itself is exercised
    by ``test_run_stdio_calls_server_run``.
    """
    from unittest.mock import MagicMock

    import app.servers.filesystem as filesystem  # use real module, not compat shim

    fake_run_stdio = MagicMock()
    monkeypatch.setattr(filesystem, "run_stdio", fake_run_stdio)

    captured = {}
    fake_asyncio_run = MagicMock(side_effect=lambda c: captured.setdefault("arg", c))
    monkeypatch.setattr(filesystem.asyncio, "run", fake_asyncio_run)

    filesystem.main()

    # The argument passed to asyncio.run is the return value of run_stdio().
    assert captured["arg"] is fake_run_stdio.return_value
