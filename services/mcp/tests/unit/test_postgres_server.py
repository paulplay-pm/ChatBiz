"""Unit tests for the postgres MCP server.

Covers 4 scenarios from the spec:

* SELECT 成功
* INSERT 拒绝 raise ``McpSecurityError``
* 超时 raise ``McpTimeoutError``
* 超行数截断

Plus full coverage on the surrounding glue: ``_read_config`` (all 3
required vars + defaults), ``_assert_readonly`` (allowed + every
forbidden prefix), ``_AuditClient.build_payload``, the respx-mocked
HTTP egress, ``_build_server`` (3 tools + ``call_tool`` dispatch +
security/timeout error paths), and the lifecycle helpers
(``_set_pool`` / ``_close_pool`` / ``_set_audit_client``).
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest
import respx
from httpx import Response
from mcp.types import CallToolRequest, ListToolsRequest, Tool

from app.servers.postgres import (
    McpSecurityError,
    McpTimeoutError,
    _assert_readonly,
    _AuditClient,
    _build_pool,
    _build_server,
    _close_pool,
    _describe_table_impl,
    _execute_query_impl,
    _get_audit_client,
    _list_tables_impl,
    _PoolHolder,
    _pool_holder,
    _read_config,
    _set_audit_client,
    _set_pool,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


REQUIRED_ENV = {
    "MCP_PG_READONLY_USER": "mcp_reader",
    "MCP_PG_READONLY_PASSWORD": "s3cret",
    "MCP_PG_DSN": "postgres://localhost:5432/chatbiz",
}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch):
    """Reset the env + singletons so each test sees a known baseline."""
    for k in list(os.environ):
        if k.startswith("MCP_"):
            monkeypatch.delenv(k, raising=False)
    for k, v in REQUIRED_ENV.items():
        monkeypatch.setenv(k, v)
    # Reset the audit-client singleton to None so each test rebuilds it.
    import app.servers.postgres as pg

    pg._audit_client = None
    yield


def _make_pool(
    fetch_return: Any = None, fetch_side_effect: Exception | None = None
) -> MagicMock:
    """Build a mock asyncpg.Pool with the chainable acquire/transaction/execute.

    ``fetch_return`` is what ``conn.fetch()`` returns (or the side effect).
    """
    conn = MagicMock()
    conn.execute = AsyncMock()
    if fetch_side_effect is not None:
        conn.fetch = AsyncMock(side_effect=fetch_side_effect)
    else:
        conn.fetch = AsyncMock(return_value=fetch_return)
    # transaction(readonly=True) is an async context manager
    tx_cm = MagicMock()
    tx_cm.__aenter__ = AsyncMock(return_value=tx_cm)
    tx_cm.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=tx_cm)
    # pool.acquire() is an async context manager
    pool = MagicMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool


@pytest.fixture
def fake_pool() -> MagicMock:
    return _make_pool()


@pytest.fixture
def mock_audit() -> MagicMock:
    """Patch the audit-egress singleton with a mock client."""
    client = MagicMock(spec=_AuditClient)
    client.post = AsyncMock()
    client.build_payload = MagicMock(
        side_effect=lambda **kw: {
            "trace_id": kw["trace_id"],
            "tool": kw["tool"],
            "ok": kw["ok"],
            "error_class": kw["error_class"],
            **(kw.get("extra") or {}),
        }
    )
    _set_audit_client(client)
    return client


# ---------------------------------------------------------------------------
# _read_config
# ---------------------------------------------------------------------------


class TestReadConfig:
    def test_returns_user_password_dsn(self):
        cfg = _read_config()
        assert cfg["user"] == "mcp_reader"
        assert cfg["password"] == "s3cret"
        assert cfg["dsn"] == "postgres://localhost:5432/chatbiz"

    def test_default_timeout_30(self):
        cfg = _read_config()
        assert cfg["query_timeout"] == 30

    def test_default_max_rows_1000(self):
        cfg = _read_config()
        assert cfg["max_rows"] == 1000

    def test_default_audit_egress_url(self):
        cfg = _read_config()
        assert cfg["audit_egress_url"] == "http://audit-and-isolation:8000/v1/audit/archive"

    def test_custom_timeout(self, monkeypatch):
        monkeypatch.setenv("MCP_PG_QUERY_TIMEOUT", "5")
        assert _read_config()["query_timeout"] == 5

    def test_custom_max_rows(self, monkeypatch):
        monkeypatch.setenv("MCP_PG_MAX_ROWS", "42")
        assert _read_config()["max_rows"] == 42

    def test_custom_audit_url(self, monkeypatch):
        monkeypatch.setenv("MCP_AUDIT_EGRESS_URL", "http://example/audit")
        assert _read_config()["audit_egress_url"] == "http://example/audit"

    def test_missing_user(self, monkeypatch):
        monkeypatch.delenv("MCP_PG_READONLY_USER", raising=False)
        with pytest.raises(RuntimeError, match="MCP_PG_READONLY_USER"):
            _read_config()

    def test_missing_password(self, monkeypatch):
        monkeypatch.delenv("MCP_PG_READONLY_PASSWORD", raising=False)
        with pytest.raises(RuntimeError, match="MCP_PG_READONLY_PASSWORD"):
            _read_config()

    def test_missing_dsn(self, monkeypatch):
        monkeypatch.delenv("MCP_PG_DSN", raising=False)
        with pytest.raises(RuntimeError, match="MCP_PG_DSN"):
            _read_config()


# ---------------------------------------------------------------------------
# _assert_readonly
# ---------------------------------------------------------------------------


class TestAssertReadOnly:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT 1",
            "  select * from t",
            "\nSELECT id FROM users",
            "WITH cte AS (SELECT 1) SELECT * FROM cte",
        ],
    )
    def test_allows_readonly(self, sql):
        _assert_readonly(sql)  # does not raise

    @pytest.mark.parametrize(
        "sql",
        [
            "INSERT INTO t VALUES (1)",
            "update t set x=1",
            "DELETE FROM t",
            "drop table t",
            "ALTER TABLE t ADD COLUMN x int",
            "CREATE TABLE t (x int)",
            "TRUNCATE t",
            "GRANT ALL ON t TO public",
            "REVOKE ALL ON t FROM public",
        ],
    )
    def test_rejects_writes(self, sql):
        with pytest.raises(McpSecurityError):
            _assert_readonly(sql)

    def test_rejects_non_string(self):
        with pytest.raises(McpSecurityError):
            _assert_readonly(123)  # type: ignore[arg-type]

    def test_empty_string_passes(self):
        _assert_readonly("")


# ---------------------------------------------------------------------------
# _AuditClient
# ---------------------------------------------------------------------------


class TestAuditClient:
    @pytest.mark.asyncio
    async def test_post_success(self):
        with respx.mock(base_url="http://audit") as router:
            route = router.post("/v1/audit/archive").mock(
                return_value=Response(200, json={"ok": True})
            )
            client = _AuditClient("http://audit/v1/audit/archive")
            await client.post(
                {"trace_id": "abc", "tool": "x", "ok": True, "error_class": None}
            )
            assert route.called

    @pytest.mark.asyncio
    async def test_post_failure_swallowed(self):
        with respx.mock(base_url="http://audit") as router:
            router.post("/v1/audit/archive").mock(side_effect=ConnectionError("nope"))
            client = _AuditClient("http://audit/v1/audit/archive")
            # Must not raise.
            await client.post({"trace_id": "abc"})

    def test_build_payload_with_extra(self):
        client = _AuditClient("http://x")
        body = client.build_payload(
            tool="execute_query",
            ok=True,
            error_class=None,
            trace_id="t-1",
            extra={"row_count": 5, "truncated": False},
        )
        assert body["tool"] == "execute_query"
        assert body["ok"] is True
        assert body["error_class"] is None
        assert body["trace_id"] == "t-1"
        assert body["row_count"] == 5
        assert body["truncated"] is False

    def test_build_payload_without_extra(self):
        client = _AuditClient("http://x")
        body = client.build_payload(
            tool="x", ok=False, error_class="security", trace_id="t-2"
        )
        assert body == {
            "trace_id": "t-2",
            "tool": "x",
            "ok": False,
            "error_class": "security",
        }


# ---------------------------------------------------------------------------
# _get_audit_client
# ---------------------------------------------------------------------------


class TestAuditSingleton:
    def test_get_creates_singleton(self):
        c1 = _get_audit_client()
        c2 = _get_audit_client()
        assert c1 is c2
        assert isinstance(c1, _AuditClient)


# ---------------------------------------------------------------------------
# _PoolHolder
# ---------------------------------------------------------------------------


class TestPoolHolder:
    def test_get_unset_raises(self):
        h = _PoolHolder()
        with pytest.raises(RuntimeError, match="pool not initialised"):
            h.get()

    @pytest.mark.asyncio
    async def test_set_get(self):
        h = _PoolHolder()
        pool = MagicMock()
        h.set(pool)
        assert h.get() is pool

    @pytest.mark.asyncio
    async def test_close_when_set(self):
        h = _PoolHolder()
        pool = MagicMock()
        pool.close = AsyncMock()
        h.set(pool)
        await h.close()
        assert h._pool is None  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_close_when_unset(self):
        h = _PoolHolder()
        await h.close()  # must not raise


# ---------------------------------------------------------------------------
# _set_pool / _close_pool
# ---------------------------------------------------------------------------


class TestPoolHelpers:
    def test_set_pool(self, fake_pool: MagicMock):
        _set_pool(fake_pool)
        assert _pool_holder.get() is fake_pool

    @pytest.mark.asyncio
    async def test_close_pool(self, fake_pool: MagicMock):
        fake_pool.close = AsyncMock()
        _set_pool(fake_pool)
        await _close_pool()
        assert _pool_holder._pool is None  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_close_pool_when_unset(self):
        # No prior set — must not raise.
        await _close_pool()


# ---------------------------------------------------------------------------
# _build_pool
# ---------------------------------------------------------------------------


class TestBuildPool:
    @pytest.mark.asyncio
    async def test_build_pool_hits_asyncpg(self, monkeypatch):
        captured: dict[str, Any] = {}

        async def fake_create_pool(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            pool = MagicMock()
            pool.close = AsyncMock()
            return pool

        monkeypatch.setattr(asyncpg, "create_pool", fake_create_pool)
        pool = await _build_pool()
        assert pool is not None
        assert captured["kwargs"]["user"] == "mcp_reader"
        assert captured["kwargs"]["password"] == "s3cret"
        assert captured["kwargs"]["dsn"] == "postgres://localhost:5432/chatbiz"
        assert captured["kwargs"]["min_size"] == 1
        assert captured["kwargs"]["max_size"] == 4


# ---------------------------------------------------------------------------
# _execute_query_impl
# ---------------------------------------------------------------------------


class TestExecuteQuery:
    @pytest.mark.asyncio
    async def test_select_success(
        self, fake_pool: MagicMock, mock_audit: MagicMock
    ):
        fake_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
        )
        result = await _execute_query_impl(
            "SELECT id, name FROM users", pool=fake_pool
        )
        assert result == {
            "rows": [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}],
            "total_rows": 2,
        }
        execute_args = [
            c.args[0]
            for c in fake_pool.acquire.return_value.__aenter__.return_value.execute.call_args_list
        ]
        assert "SET TRANSACTION READ ONLY" in execute_args
        assert any("statement_timeout" in a for a in execute_args)

    @pytest.mark.asyncio
    async def test_insert_rejected(
        self, fake_pool: MagicMock, mock_audit: MagicMock
    ):
        with pytest.raises(McpSecurityError):
            await _execute_query_impl(
                "INSERT INTO users (name) VALUES ('hacker')", pool=fake_pool
            )
        # Pool must not be acquired for a rejected request.
        fake_pool.acquire.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_rejected(self, fake_pool: MagicMock):
        with pytest.raises(McpSecurityError):
            await _execute_query_impl("UPDATE users SET name='x'", pool=fake_pool)

    @pytest.mark.asyncio
    async def test_delete_rejected(self, fake_pool: MagicMock):
        with pytest.raises(McpSecurityError):
            await _execute_query_impl("DELETE FROM users", pool=fake_pool)

    @pytest.mark.asyncio
    async def test_query_timeout_raises(
        self, fake_pool: MagicMock, mock_audit: MagicMock
    ):
        fake_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            side_effect=asyncpg.QueryCanceledError("canceled")
        )
        with pytest.raises(McpTimeoutError):
            await _execute_query_impl("SELECT 1", pool=fake_pool)

    @pytest.mark.asyncio
    async def test_max_rows_truncation(
        self, fake_pool: MagicMock, mock_audit: MagicMock
    ):
        rows = [{"id": i} for i in range(5)]
        fake_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=rows
        )
        result = await _execute_query_impl(
            "SELECT * FROM big", pool=fake_pool, max_rows=3, query_timeout=10
        )
        assert result["truncated"] is True
        assert result["total_rows"] == 5
        assert result["rows"] == [{"id": 0}, {"id": 1}, {"id": 2}]

    @pytest.mark.asyncio
    async def test_under_max_rows_no_truncated_flag(self, fake_pool: MagicMock):
        rows = [{"id": i} for i in range(3)]
        fake_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=rows
        )
        result = await _execute_query_impl(
            "SELECT * FROM small", pool=fake_pool, max_rows=10
        )
        assert "truncated" not in result
        assert result["total_rows"] == 3
        assert result["rows"] == rows

    @pytest.mark.asyncio
    async def test_uses_default_max_rows_from_env(
        self, fake_pool: MagicMock, monkeypatch
    ):
        monkeypatch.setenv("MCP_PG_MAX_ROWS", "2")
        rows = [{"id": i} for i in range(4)]
        fake_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=rows
        )
        result = await _execute_query_impl("SELECT 1", pool=fake_pool)
        assert result["truncated"] is True
        assert len(result["rows"]) == 2
        assert result["total_rows"] == 4


# ---------------------------------------------------------------------------
# _list_tables_impl
# ---------------------------------------------------------------------------


class TestListTables:
    @pytest.mark.asyncio
    async def test_default_schema(self, fake_pool: MagicMock):
        fake_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[{"table_name": "orders"}, {"table_name": "users"}]
        )
        tables = await _list_tables_impl(pool=fake_pool)
        assert tables == ["orders", "users"]
        args = (
            fake_pool.acquire.return_value.__aenter__.return_value.fetch.call_args
        )
        assert args.args[0].startswith("SELECT table_name")
        assert args.args[1] == "public"

    @pytest.mark.asyncio
    async def test_custom_schema(self, fake_pool: MagicMock):
        fake_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[]
        )
        await _list_tables_impl(schema="audit", pool=fake_pool)
        args = (
            fake_pool.acquire.return_value.__aenter__.return_value.fetch.call_args
        )
        assert args.args[1] == "audit"

    @pytest.mark.asyncio
    async def test_uses_module_pool_when_none(self, fake_pool: MagicMock):
        _set_pool(fake_pool)
        fake_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[]
        )
        await _list_tables_impl()
        fake_pool.acquire.assert_called()


# ---------------------------------------------------------------------------
# _describe_table_impl
# ---------------------------------------------------------------------------


class TestDescribeTable:
    @pytest.mark.asyncio
    async def test_describe_returns_columns(self, fake_pool: MagicMock):
        fake_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[
                {"column_name": "id", "data_type": "integer", "is_nullable": "NO"},
                {"column_name": "name", "data_type": "text", "is_nullable": "YES"},
            ]
        )
        cols = await _describe_table_impl("users", pool=fake_pool)
        assert cols == [
            {"column_name": "id", "data_type": "integer", "is_nullable": "NO"},
            {"column_name": "name", "data_type": "text", "is_nullable": "YES"},
        ]
        args = (
            fake_pool.acquire.return_value.__aenter__.return_value.fetch.call_args
        )
        assert args.args[1] == "public"
        assert args.args[2] == "users"

    @pytest.mark.asyncio
    async def test_describe_custom_schema(self, fake_pool: MagicMock):
        fake_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[]
        )
        await _describe_table_impl("events", schema="audit", pool=fake_pool)
        args = (
            fake_pool.acquire.return_value.__aenter__.return_value.fetch.call_args
        )
        assert args.args[1] == "audit"
        assert args.args[2] == "events"


# ---------------------------------------------------------------------------
# _build_server + call_tool dispatch
# ---------------------------------------------------------------------------


def _list_tools(server) -> list[Tool]:
    """Helper to invoke the server's ``list_tools`` handler and return the list."""
    import asyncio

    handler = server.request_handlers[ListToolsRequest]
    func = _extract_inner_func(handler)
    return asyncio.run(func())


def _extract_inner_func(handler) -> Any:
    """Return the user's async function from a decorated MCP handler."""
    if hasattr(handler, "__wrapped__"):
        return handler.__wrapped__
    closure = handler.__closure__ or ()
    for cell in closure:
        candidate = cell.cell_contents
        if callable(candidate) and not isinstance(candidate, type):
            return candidate
    raise RuntimeError("could not extract inner function from handler")


class TestBuildServer:
    def test_server_name(self):
        server = _build_server()
        assert server.name == "chatbiz-mcp-postgres"

    def test_lists_three_tools(self):
        server = _build_server()
        tools = _list_tools(server)
        names = {t.name for t in tools}
        assert names == {"execute_query", "list_tables", "describe_table"}

    def test_tool_schemas(self):
        server = _build_server()
        tools = _list_tools(server)
        by_name = {t.name: t for t in tools}
        assert "sql" in by_name["execute_query"].inputSchema["properties"]
        assert "schema" in by_name["list_tables"].inputSchema["properties"]
        assert "table_name" in by_name["describe_table"].inputSchema["properties"]
        assert "schema" in by_name["describe_table"].inputSchema["properties"]


def _call_tool(server, name: str, arguments: dict[str, Any]):
    """Invoke the server's ``call_tool`` handler and return its result.

    The inner async function is extracted from the handler's closure
    and awaited via ``asyncio.run`` so that this works from plain
    (non-async) test methods.
    """
    import asyncio

    handler = server.request_handlers[CallToolRequest]
    func = _extract_inner_func(handler)
    return asyncio.run(func(name, arguments))


class TestCallToolDispatch:
    def test_execute_query_dispatches_and_audits(
        self, fake_pool: MagicMock, mock_audit: MagicMock
    ):
        fake_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[{"id": 1}]
        )
        _set_pool(fake_pool)
        server = _build_server()
        results = _call_tool(
            server,
            "execute_query",
            {"sql": "SELECT id FROM users", "trace_id": "trace-1"},
        )
        assert any("id" in r.text for r in results)
        mock_audit.post.assert_called_once()
        # The audit payload should mention execute_query + row_count.
        payload = mock_audit.build_payload.call_args.kwargs
        assert payload["tool"] == "execute_query"
        assert payload["ok"] is True

    def test_list_tables_dispatches_and_audits(
        self, fake_pool: MagicMock, mock_audit: MagicMock
    ):
        fake_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[{"table_name": "t1"}]
        )
        _set_pool(fake_pool)
        server = _build_server()
        results = _call_tool(
            server, "list_tables", {"schema": "public", "trace_id": "trace-2"}
        )
        assert any("t1" in r.text for r in results)
        mock_audit.post.assert_called_once()
        payload = mock_audit.build_payload.call_args.kwargs
        assert payload["tool"] == "list_tables"

    def test_describe_table_dispatches_and_audits(
        self, fake_pool: MagicMock, mock_audit: MagicMock
    ):
        fake_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            return_value=[{"column_name": "id", "data_type": "int", "is_nullable": "NO"}]
        )
        _set_pool(fake_pool)
        server = _build_server()
        results = _call_tool(
            server,
            "describe_table",
            {"table_name": "users", "schema": "public", "trace_id": "trace-3"},
        )
        assert any("id" in r.text for r in results)
        mock_audit.post.assert_called_once()
        payload = mock_audit.build_payload.call_args.kwargs
        assert payload["tool"] == "describe_table"

    def test_unknown_tool_raises(self, mock_audit: MagicMock):
        server = _build_server()
        with pytest.raises(ValueError, match="unknown tool"):
            _call_tool(server, "no_such_tool", {})

    def test_security_error_audits_and_raises(
        self, fake_pool: MagicMock, mock_audit: MagicMock
    ):
        # INSERT is rejected by the security check — no DB call.
        server = _build_server()
        with pytest.raises(McpSecurityError):
            _call_tool(server, "execute_query", {"sql": "INSERT INTO t VALUES (1)"})
        # Audit was posted with error_class=security.
        mock_audit.post.assert_called_once()
        payload = mock_audit.build_payload.call_args.kwargs
        assert payload["error_class"] == "security"
        assert payload["ok"] is False

    def test_timeout_error_audits_and_raises(
        self, fake_pool: MagicMock, mock_audit: MagicMock
    ):
        fake_pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
            side_effect=asyncpg.QueryCanceledError("canceled")
        )
        _set_pool(fake_pool)
        server = _build_server()
        with pytest.raises(McpTimeoutError):
            _call_tool(server, "execute_query", {"sql": "SELECT 1"})
        mock_audit.post.assert_called_once()
        payload = mock_audit.build_payload.call_args.kwargs
        assert payload["error_class"] == "timeout"
        assert payload["ok"] is False


# ---------------------------------------------------------------------------
# Stdio entry point: _run() + main()
# ---------------------------------------------------------------------------


class TestStdioEntry:
    @pytest.mark.asyncio
    async def test_run_builds_pool_and_runs_server(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # Avoid actually starting the stdio transport or talking to PG.
        started = {"server": None, "pool": None}

        async def fake_build_pool():
            pool = MagicMock()
            pool.close = AsyncMock()
            started["pool"] = pool
            return pool

        def fake_stdio_server():
            # Return an async context manager yielding two dummy streams.
            class _CM:
                async def __aenter__(self):
                    return (MagicMock(), MagicMock())

                async def __aexit__(self, *exc):
                    return None

            return _CM()

        server_obj = MagicMock()
        server_obj.run = AsyncMock()
        server_obj.create_initialization_options = MagicMock(return_value="opts")

        monkeypatch.setattr("app.servers.postgres._build_pool", fake_build_pool)
        monkeypatch.setattr("app.servers.postgres.stdio_server", fake_stdio_server)
        monkeypatch.setattr(
            "app.servers.postgres._build_server", lambda: server_obj
        )

        from app.servers.postgres import _run

        await _run()

        assert started["pool"] is not None
        server_obj.run.assert_awaited_once()

    def test_main_invokes_run(self, monkeypatch: pytest.MonkeyPatch):
        called = {"flag": False}

        async def fake_run():
            called["flag"] = True

        monkeypatch.setattr("app.servers.postgres._run", fake_run)
        monkeypatch.setattr("app.servers.postgres.logging", MagicMock())

        from app.servers.postgres import main

        main()
        assert called["flag"] is True
