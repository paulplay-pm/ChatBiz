"""Best-effort audit egress helpers for MCP tool calls.

All MCP tool calls must be mirrored to the audit-and-isolation service
(eng-review Arch #1: egress enforcement). Audit failures are Fail-Open:
we log/drop the audit failure but never break the tool's primary
response.
"""

from __future__ import annotations

from collections.abc import Callable, Awaitable
from typing import Any

import httpx

DEFAULT_AUDIT_URL = "http://localhost:8080/v1/mcp/audit"


def make_audit_call(
    *,
    tool_name: str,
    user_id: str,
    trace_id: str,
    payload: dict[str, Any],
    status_code: int,
    latency_ms: int,
    audit_url: str | None = None,
) -> Callable[[], Awaitable[None]]:
    """Return an async no-arg callable that posts one audit event.

    The indirection matches the fetch-server subagent contract and lets
    tests patch / invoke the audit call explicitly.
    """

    async def _call() -> None:
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
                await client.post(audit_url or DEFAULT_AUDIT_URL, json=body)
        except httpx.HTTPError:
            # Fail-Open: audit loss should never break the primary MCP tool call.
            return

    return _call


__all__ = ["DEFAULT_AUDIT_URL", "make_audit_call"]
