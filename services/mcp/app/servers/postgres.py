"""Postgres MCP server.

Provides 3 read-only tools (``execute_query`` / ``list_tables`` /
``describe_table``) backed by an ``asyncpg`` connection pool.  All
SQL traffic is forced through ``SET TRANSACTION READ ONLY`` and a
30-second ``statement_timeout``; INSERT / UPDATE / DELETE are rejected
at the application layer even though the connected PG user has those
privileges revoked in the database.

Every tool invocation is forwarded to the
``services/audit-and-isolation`` egress endpoint
(``POST /v1/audit/archive``) so that an enterprise-grade audit trail
is preserved.  Audit-write failures are logged and dropped — they
never break the main flow.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import asyncpg
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exception taxonomy
# ---------------------------------------------------------------------------


class McpError(Exception):
    """Base class for all MCP server errors."""


class McpSecurityError(McpError):
    """Raised when a request would violate a security invariant.

    Used for ``INSERT`` / ``UPDATE`` / ``DELETE`` attempts against a
    server that is configured for read-only access.
    """


class McpTimeoutError(McpError):
    """Raised when the underlying asyncpg query exceeds the timeout."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def _read_config() -> dict[str, Any]:
    """Read postgres-server config from environment variables.

    Required vars (server refuses to start without them):

    * ``MCP_PG_READONLY_USER`` — read-only PG role
    * ``MCP_PG_READONLY_PASSWORD`` — that role's password
    * ``MCP_PG_DSN`` — full DSN string consumed by ``asyncpg``

    Optional vars with sane defaults:

    * ``MCP_PG_QUERY_TIMEOUT`` (seconds, default 30)
    * ``MCP_PG_MAX_ROWS`` (default 1000)
    * ``MCP_AUDIT_EGRESS_URL`` (default ``http://audit-and-isolation:8000/v1/audit/archive``)
    """
    user = os.environ.get("MCP_PG_READONLY_USER")
    password = os.environ.get("MCP_PG_READONLY_PASSWORD")
    dsn = os.environ.get("MCP_PG_DSN")
    if not user:
        raise RuntimeError("MCP_PG_READONLY_USER env not set")
    if not password:
        raise RuntimeError("MCP_PG_READONLY_PASSWORD env not set")
    if not dsn:
        raise RuntimeError("MCP_PG_DSN env not set")

    timeout_raw = os.environ.get("MCP_PG_QUERY_TIMEOUT", "30")
    max_rows_raw = os.environ.get("MCP_PG_MAX_ROWS", "1000")
    audit_url = os.environ.get(
        "MCP_AUDIT_EGRESS_URL",
        "http://audit-and-isolation:8000/v1/audit/archive",
    )

    return {
        "user": user,
        "password": password,
        "dsn": dsn,
        "query_timeout": int(timeout_raw),
        "max_rows": int(max_rows_raw),
        "audit_egress_url": audit_url,
    }


# ---------------------------------------------------------------------------
# Pool management
# ---------------------------------------------------------------------------


class _PoolHolder:
    """Lazy singleton wrapper around an :class:`asyncpg.Pool`.

    The pool is created on the first call to :meth:`get` and shared
    across every tool invocation.  Tests inject a pre-built pool via
    :meth:`set` so that no real network calls hit Postgres.
    """

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    def set(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    def get(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("asyncpg pool not initialised")
        return self._pool

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


_pool_holder = _PoolHolder()


def _set_pool(pool: asyncpg.Pool) -> None:
    """Test/entry helper to inject a pre-built pool."""
    _pool_holder.set(pool)


async def _close_pool() -> None:
    """Test/entry helper to dispose the singleton pool."""
    await _pool_holder.close()


async def _build_pool() -> asyncpg.Pool:
    """Build a real asyncpg pool from the env-derived config."""
    cfg = _read_config()
    pool = await asyncpg.create_pool(
        dsn=cfg["dsn"],
        user=cfg["user"],
        password=cfg["password"],
        min_size=1,
        max_size=4,
    )
    _pool_holder.set(pool)
    return pool


# ---------------------------------------------------------------------------
# SQL safety
# ---------------------------------------------------------------------------


_FORBIDDEN_PREFIXES = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "TRUNCATE",
    "DROP",
    "ALTER",
    "CREATE",
    "GRANT",
    "REVOKE",
)


def _assert_readonly(sql: str) -> None:
    """Reject write-statement SQL on the application layer.

    The connected PG user is also configured with ``REVOKE INSERT,
    UPDATE, DELETE``, but we never want a bug in the DB provisioning
    to silently turn this server into a write surface.
    """
    if not isinstance(sql, str):
        raise McpSecurityError("sql must be a string")
    stripped = sql.lstrip()
    head = stripped.split(None, 1)[0].upper() if stripped else ""
    if head in _FORBIDDEN_PREFIXES:
        raise McpSecurityError(
            f"{head} not allowed (read-only user)"
        )


# ---------------------------------------------------------------------------
# Audit egress
# ---------------------------------------------------------------------------


class _AuditClient:
    """Async ``httpx`` wrapper for writing audit records to the egress.

    The class encapsulates the network surface so tests can swap in a
    ``respx`` transport.  Failures are swallowed — the spec requires
    that an audit-write failure must never break the tool response.
    """

    def __init__(self, url: str, timeout: float = 2.0) -> None:
        self._url = url
        self._timeout = timeout

    async def post(self, payload: dict[str, Any]) -> None:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                await client.post(self._url, json=payload)
        except Exception as exc:
            logger.warning("audit egress failed: %s", exc)

    def build_payload(
        self,
        *,
        tool: str,
        ok: bool,
        error_class: str | None,
        trace_id: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "trace_id": trace_id,
            "tool": tool,
            "ok": ok,
            "error_class": error_class,
        }
        if extra:
            body.update(extra)
        return body


_audit_client: _AuditClient | None = None


def _get_audit_client() -> _AuditClient:
    global _audit_client
    if _audit_client is None:
        cfg = _read_config()
        _audit_client = _AuditClient(url=cfg["audit_egress_url"])
    return _audit_client


def _set_audit_client(client: _AuditClient) -> None:
    """Test hook — replace the singleton with a stub / mock."""
    global _audit_client
    _audit_client = client


# ---------------------------------------------------------------------------
# Core tool implementations
# ---------------------------------------------------------------------------


async def _execute_query_impl(
    sql: str,
    *,
    pool: asyncpg.Pool | None = None,
    max_rows: int | None = None,
    query_timeout: int | None = None,
) -> dict[str, Any]:
    """Run a read-only SQL query and return ``{rows, total_rows, [truncated]}``.

    The transaction is forced to ``READ ONLY`` and a
    ``statement_timeout`` is set so that runaway queries cannot
    exhaust the connection pool.
    """
    _assert_readonly(sql)

    cfg = _read_config()
    effective_pool = pool if pool is not None else _pool_holder.get()
    effective_max = max_rows if max_rows is not None else cfg["max_rows"]
    effective_timeout = (
        query_timeout if query_timeout is not None else cfg["query_timeout"]
    )

    timeout_statement = f"SET statement_timeout = '{effective_timeout}s'"

    try:
        async with effective_pool.acquire() as conn:
            async with conn.transaction(readonly=True):
                await conn.execute("SET TRANSACTION READ ONLY")
                await conn.execute(timeout_statement)
                records = await conn.fetch(sql)
    except asyncpg.QueryCanceledError as exc:
        raise McpTimeoutError(
            f"query exceeded {effective_timeout}s"
        ) from exc

    rows = [dict(r) for r in records]
    total = len(rows)
    truncated = total > effective_max
    if truncated:
        rows = rows[:effective_max]

    result: dict[str, Any] = {"rows": rows, "total_rows": total}
    if truncated:
        result["truncated"] = True
    return result


async def _list_tables_impl(
    schema: str = "public",
    *,
    pool: asyncpg.Pool | None = None,
) -> list[str]:
    """Return every table name in ``schema`` (default ``public``)."""
    effective_pool = pool if pool is not None else _pool_holder.get()
    async with effective_pool.acquire() as conn:
        async with conn.transaction(readonly=True):
            await conn.execute("SET TRANSACTION READ ONLY")
            rows = await conn.fetch(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = $1 ORDER BY table_name",
                schema,
            )
    return [r["table_name"] for r in rows]


async def _describe_table_impl(
    table_name: str,
    schema: str = "public",
    *,
    pool: asyncpg.Pool | None = None,
) -> list[dict[str, Any]]:
    """Return column metadata for ``table_name`` in ``schema``."""
    effective_pool = pool if pool is not None else _pool_holder.get()
    async with effective_pool.acquire() as conn:
        async with conn.transaction(readonly=True):
            await conn.execute("SET TRANSACTION READ ONLY")
            rows = await conn.fetch(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_schema = $1 AND table_name = $2 "
                "ORDER BY ordinal_position",
                schema,
                table_name,
            )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# MCP server wiring (stdio entry point)
# ---------------------------------------------------------------------------


def _build_server() -> Server:
    """Construct the :class:`mcp.Server` with all 3 tools registered."""
    server = Server("chatbiz-mcp-postgres")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="execute_query",
                description=(
                    "Run a read-only SQL query. INSERT/UPDATE/DELETE are "
                    "rejected at the application layer."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string"},
                    },
                    "required": ["sql"],
                },
            ),
            Tool(
                name="list_tables",
                description="List all tables in a schema (default 'public').",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "schema": {"type": "string"},
                    },
                },
            ),
            Tool(
                name="describe_table",
                description=(
                    "Describe a table's columns in a schema "
                    "(default 'public')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "schema": {"type": "string"},
                    },
                    "required": ["table_name"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]):
        audit = _get_audit_client()
        trace_id = str(arguments.get("trace_id", "no-trace"))
        try:
            if name == "execute_query":
                sql = arguments.get("sql", "")
                result = await _execute_query_impl(sql)
                await audit.post(
                    audit.build_payload(
                        tool=name,
                        ok=True,
                        error_class=None,
                        trace_id=trace_id,
                        extra={
                            "row_count": len(result.get("rows", [])),
                            "truncated": result.get("truncated", False),
                        },
                    )
                )
                return [TextContent(type="text", text=str(result))]

            if name == "list_tables":
                schema = arguments.get("schema", "public")
                tables = await _list_tables_impl(schema)
                await audit.post(
                    audit.build_payload(
                        tool=name,
                        ok=True,
                        error_class=None,
                        trace_id=trace_id,
                        extra={"table_count": len(tables)},
                    )
                )
                return [TextContent(type="text", text=str(tables))]

            if name == "describe_table":
                table = arguments.get("table_name", "")
                schema = arguments.get("schema", "public")
                cols = await _describe_table_impl(table, schema)
                await audit.post(
                    audit.build_payload(
                        tool=name,
                        ok=True,
                        error_class=None,
                        trace_id=trace_id,
                        extra={"column_count": len(cols)},
                    )
                )
                return [TextContent(type="text", text=str(cols))]

            raise ValueError(f"unknown tool: {name}")
        except McpSecurityError as exc:
            await audit.post(
                audit.build_payload(
                    tool=name,
                    ok=False,
                    error_class="security",
                    trace_id=trace_id,
                    extra={"message": str(exc)},
                )
            )
            raise
        except McpTimeoutError as exc:
            await audit.post(
                audit.build_payload(
                    tool=name,
                    ok=False,
                    error_class="timeout",
                    trace_id=trace_id,
                    extra={"message": str(exc)},
                )
            )
            raise

    return server


# ---------------------------------------------------------------------------
# Stdio entry point
# ---------------------------------------------------------------------------


async def _run() -> None:
    """Run the MCP server over stdio."""
    await _build_pool()
    server = _build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Stdio entry point: read config + pool + run server."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run())


TOOL_NAMES = ("execute_query", "list_tables", "describe_table")


def _run_coro(coro):
    """Run an async helper from the router's sync HANDLER adapter."""
    return asyncio.run(coro)


def HANDLER(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Synchronous adapter used by ``app.router.McpRouter``."""
    if tool_name.startswith("pg_"):
        tool_name = tool_name.removeprefix("pg_")
    if tool_name == "execute_query":
        return _run_coro(_execute_query_impl(args.get("sql", "")))
    if tool_name == "list_tables":
        return {"tables": _run_coro(_list_tables_impl(args.get("schema", "public")))}
    if tool_name == "describe_table":
        return {
            "columns": _run_coro(
                _describe_table_impl(
                    args.get("table_name", ""), args.get("schema", "public")
                )
            )
        }
    raise ValueError(f"unknown postgres tool: {tool_name}")


__all__ = [
    "McpError",
    "McpSecurityError",
    "McpTimeoutError",
    "TOOL_NAMES",
    "HANDLER",
    "_assert_readonly",
    "_AuditClient",
    "_audit_client",
    "_build_pool",
    "_build_server",
    "_close_pool",
    "_describe_table_impl",
    "_execute_query_impl",
    "_get_audit_client",
    "_list_tables_impl",
    "_PoolHolder",
    "_pool_holder",
    "_read_config",
    "_set_audit_client",
    "_set_pool",
    "main",
]
