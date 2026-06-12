"""filesystem MCP server.

Provides 4 stdio-MCP tools over the ``mcp[cli]`` library, all gated by
the directory whitelist configured via ``MCP_FS_ALLOWED_DIRS``. Every
tool call is mirrored to the audit-and-isolation egress via ``httpx``
(eng-review #1 — MCP calls MUST traverse the audit gateway so PII
scanning + trace-id correlation are preserved).

Tool list (locked by ``openspec/changes/mcp-server-integration-mvp/
specs/mcp-filesystem-server/spec.md``):

* ``read_file(path: str) -> str`` — return file contents.
* ``write_file(path: str, content: str) -> dict`` — write file + audit.
* ``list_dir(path: str) -> list[str]`` — list immediate children.
* ``search(path: str, pattern: str) -> list[str]`` — glob search.

Failure modes:

* ``McpSecurityError`` — path is outside the whitelist or the
  whitelist env is unset at startup. The MCP response body carries
  ``error_class: "security"`` per the spec.
* Audit egress failure — logged at WARNING, does NOT raise (the tool
  itself must still succeed; audit loss is acceptable, tool failure is
  not).
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Sequence

import httpx
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions

from app.security import McpSecurityError, McpSecurityPolicy
from mcp.server.stdio import stdio_server

logger = logging.getLogger(__name__)

SERVER_NAME = "chatbiz-mcp-filesystem"
SERVER_VERSION = "0.1.0"


# ---------------------------------------------------------------------------
# Audit egress
# ---------------------------------------------------------------------------


async def _post_audit(audit_url: str, payload: dict[str, Any]) -> None:
    """POST one audit row to the audit-and-isolation egress.

    Audit loss is acceptable; tool failure is not. Any HTTP / network
    error is caught and logged at WARNING.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(audit_url, json=payload)
    except Exception as e:
        logger.warning(
            f"audit egress failed for action={payload.get('action')} "
            f"trace_id={payload.get('trace_id')}: {e}"
        )


def _audit_payload(
    action: str,
    resolved_path: Path,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical audit row body for a tool call."""
    payload: dict[str, Any] = {
        "trace_id": uuid.uuid4().hex,
        "service": "mcp-filesystem",
        "action": action,
        "path": str(resolved_path),
    }
    if extra:
        payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def _read_file_impl(path: str, policy: McpSecurityPolicy) -> str:
    resolved = policy.check_path(path)
    return resolved.read_text(encoding="utf-8")


def _write_file_impl(path: str, content: str, policy: McpSecurityPolicy) -> dict[str, Any]:
    resolved = policy.check_path(path)
    resolved.write_text(content, encoding="utf-8")
    return {
        "path": str(resolved),
        "bytes": resolved.stat().st_size,
    }


def _list_dir_impl(path: str, policy: McpSecurityPolicy) -> list[str]:
    resolved = policy.check_path(path)
    if not resolved.is_dir():
        raise McpSecurityError(f"not a directory: {resolved}")
    return sorted(p.name for p in resolved.iterdir())


def _search_impl(path: str, pattern: str, policy: McpSecurityPolicy) -> list[str]:
    resolved = policy.check_path(path)
    if not resolved.is_dir():
        raise McpSecurityError(f"not a directory: {resolved}")
    matches: list[str] = []
    for p in resolved.rglob("*"):
        if fnmatch.fnmatch(p.name, pattern):
            matches.append(str(p))
    return sorted(matches)


# ---------------------------------------------------------------------------
# Server factory + tool dispatch
# ---------------------------------------------------------------------------


def _tool_schemas() -> list[types.Tool]:
    """Static list of the 4 MCP tool descriptors."""
    return [
        types.Tool(
            name="read_file",
            description="Read a UTF-8 text file. Path MUST be inside MCP_FS_ALLOWED_DIRS.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "absolute file path"},
                },
                "required": ["path"],
            },
        ),
        types.Tool(
            name="write_file",
            description="Write a UTF-8 text file. Path MUST be inside MCP_FS_ALLOWED_DIRS. Audited.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        ),
        types.Tool(
            name="list_dir",
            description="List immediate children of a directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
        ),
        types.Tool(
            name="search",
            description="Glob search under a directory (e.g. '*.txt').",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "pattern": {"type": "string", "description": "glob pattern"},
                },
                "required": ["path", "pattern"],
            },
        ),
    ]


def build_server(
    policy: McpSecurityPolicy | None = None,
    audit_url: str | None = None,
) -> Server:
    """Build the MCP ``Server`` object for the filesystem server.

    Reads ``MCP_FS_ALLOWED_DIRS`` and ``MCP_AUDIT_URL`` from the
    environment on first call. Raises ``McpSecurityError`` if
    ``MCP_FS_ALLOWED_DIRS`` is missing — never defaults to "allow
    everything".
    """
    if policy is None:
        policy = McpSecurityPolicy.from_env()
    if audit_url is None:
        audit_url = os.environ.get("MCP_AUDIT_URL", "")

    server: Server = Server(SERVER_NAME)

    async def _dispatch(
        name: str, arguments: dict[str, Any]
    ) -> Sequence[types.TextContent]:
        """Route a CallToolRequest to the right impl + audit.

        Exposed on ``server._dispatch`` so tests can invoke it
        directly without spinning up the stdio transport.
        """
        path = arguments["path"]

        if name == "read_file":
            try:
                resolved_for_audit = policy.check_path(path)
            except McpSecurityError:
                await _post_audit(
                    audit_url,
                    _audit_payload("read_file_denied", Path(path), {"reason": "outside whitelist"}),
                )
                raise
            try:
                text = _read_file_impl(path, policy)
            except Exception as e:
                await _post_audit(
                    audit_url,
                    _audit_payload("read_file_error", resolved_for_audit, {"error": str(e)}),
                )
                raise
            await _post_audit(
                audit_url,
                _audit_payload("read_file", resolved_for_audit, {"bytes": len(text)}),
            )
            return [types.TextContent(type="text", text=text)]

        if name == "write_file":
            content = arguments["content"]
            try:
                resolved_for_audit = policy.check_path(path)
            except McpSecurityError:
                await _post_audit(
                    audit_url,
                    _audit_payload("write_file_denied", Path(path), {"reason": "outside whitelist"}),
                )
                raise
            info = _write_file_impl(path, content, policy)
            await _post_audit(
                audit_url,
                _audit_payload("write_file", resolved_for_audit, {"bytes": info["bytes"]}),
            )
            return [types.TextContent(type="text", text=f"wrote {info['bytes']} bytes")]

        if name == "list_dir":
            try:
                resolved_for_audit = policy.check_path(path)
            except McpSecurityError:
                await _post_audit(
                    audit_url,
                    _audit_payload("list_dir_denied", Path(path), {"reason": "outside whitelist"}),
                )
                raise
            try:
                entries = _list_dir_impl(path, policy)
            except Exception as e:
                await _post_audit(
                    audit_url,
                    _audit_payload("list_dir_error", resolved_for_audit, {"error": str(e)}),
                )
                raise
            await _post_audit(
                audit_url,
                _audit_payload("list_dir", resolved_for_audit, {"count": len(entries)}),
            )
            return [types.TextContent(type="text", text="\n".join(entries))]

        if name == "search":
            pattern = arguments["pattern"]
            try:
                resolved_for_audit = policy.check_path(path)
            except McpSecurityError:
                await _post_audit(
                    audit_url,
                    _audit_payload("search_denied", Path(path), {"reason": "outside whitelist"}),
                )
                raise
            try:
                matches = _search_impl(path, pattern, policy)
            except Exception as e:
                await _post_audit(
                    audit_url,
                    _audit_payload("search_error", resolved_for_audit, {"error": str(e)}),
                )
                raise
            await _post_audit(
                audit_url,
                _audit_payload(
                    "search",
                    resolved_for_audit,
                    {"pattern": pattern, "count": len(matches)},
                ),
            )
            return [types.TextContent(type="text", text="\n".join(matches))]

        raise ValueError(f"unknown tool: {name}")

    # Expose the dispatch coroutine on the server object so tests can
    # call it directly without going through the stdio transport.
    server._dispatch = _dispatch  # type: ignore[attr-defined]
    server._policy = policy
    server._audit_url = audit_url

    @server.list_tools()
    async def _list_tools_handler() -> list[types.Tool]:
        return _tool_schemas()

    @server.call_tool()
    async def _call_tool_handler(
        name: str, arguments: dict[str, Any]
    ) -> Sequence[types.TextContent]:
        return await _dispatch(name, arguments)

    return server


async def run_stdio() -> None:
    """Production entrypoint: build + run the server on stdio."""
    from mcp.server import NotificationOptions

    server = build_server()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=SERVER_NAME,
                server_version=SERVER_VERSION,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main() -> None:
    """Console-script entrypoint (``python -m servers.filesystem``)."""
    asyncio.run(run_stdio())


__all__ = [
    "SERVER_NAME",
    "SERVER_VERSION",
    "build_server",
    "run_stdio",
    "main",
    "_tool_schemas",
]
