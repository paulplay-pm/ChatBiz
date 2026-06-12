"""fetch MCP server stub (skeleton phase).

Real implementation (task 4.1) will expose ``fetch_url`` /
``fetch_html`` / ``fetch_json`` with URL allowlist + SSRF defense.
This stub provides a callable the router can invoke for ``fetch_*``
tool names during skeleton-phase end-to-end testing.
"""

from __future__ import annotations

from typing import Any

__all__ = ["HANDLER", "TOOL_NAMES"]


TOOL_NAMES: tuple[str, ...] = ("fetch_stub",)


def HANDLER(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Skeleton-phase stub handler for fetch tools."""
    return {"server": "fetch", "tool": tool_name, "args": args, "ok": True}