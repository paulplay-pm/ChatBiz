"""MCP router (skeleton — extended by router worktree).

The router worktree owns the JSON-RPC-over-stdio dispatch loop.
This minimal version exposes the symbols the fetch server relies
on (``make_audit_call`` / ``audit_call``) so the subagent contract
holds even before the router is fully wired.
"""

from __future__ import annotations

import os
from typing import Awaitable, Callable

import httpx

__all__ = ["audit_call", "make_audit_call"]


async def audit_call(
    *,
    audit_url: str,
    tool_name: str,
    user_id: str,
    trace_id: str,
    payload: dict,
    status_code: int,
    latency_ms: int,
) -> None:
    """Best-effort write of a single MCP-tool audit record.

    The full audit-and-isolation egress integration lives in the
    router worktree. This helper is the fetch subagent's safe
    dependency: it never raises (audit-write failure MUST NOT
    block the tool result), and it accepts an explicit ``audit_url``
    so the test can substitute a ``respx`` mock.
    """
    body = {
        "tool_name": tool_name,
        "user_id": user_id,
        "trace_id": trace_id,
        "payload": payload,
        "status_code": status_code,
        "latency_ms": latency_ms,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(audit_url, json=body)
    except Exception:
        # Audit write MUST NOT block the tool response.
        # The router worktree handles structured logging.
        pass


def make_audit_call(
    *,
    tool_name: str,
    user_id: str,
    trace_id: str,
    payload: dict,
    status_code: int,
    latency_ms: int,
    audit_url: str | None = None,
) -> Callable[[], Awaitable[None]]:
    """Return a no-arg coroutine factory for a single audit write.

    The fetch server invokes this once per tool call so the audit
    I/O is decoupled from the response-building path. When
    ``audit_url`` is not supplied the URL is resolved from
    ``MCP_AUDIT_URL`` (defaulting to ``http://localhost:8080/v1/mcp/audit``,
    the canonical constant owned by the router worktree).
    """
    resolved_url = (
        audit_url
        if audit_url is not None
        else os.environ.get("MCP_AUDIT_URL", "http://localhost:8080/v1/mcp/audit")
    )

    async def _do() -> None:
        await audit_call(
            audit_url=resolved_url,
            tool_name=tool_name,
            user_id=user_id,
            trace_id=trace_id,
            payload=payload,
            status_code=status_code,
            latency_ms=latency_ms,
        )

    return _do