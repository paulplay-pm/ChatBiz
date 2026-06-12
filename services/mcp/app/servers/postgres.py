"""postgres MCP server stub (skeleton phase).

Real implementation (task 5.1) will expose ``execute_query`` /
``list_tables`` / ``describe_table`` using the dedicated read-only
PG user and ``SET TRANSACTION READ ONLY``. This stub provides a
callable the router can invoke for ``pg_*`` tool names during
skeleton-phase end-to-end testing.
"""

from __future__ import annotations

from typing import Any

__all__ = ["HANDLER", "TOOL_NAMES"]


TOOL_NAMES: tuple[str, ...] = ("pg_stub",)


def HANDLER(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Skeleton-phase stub handler for postgres tools."""
    return {"server": "postgres", "tool": tool_name, "args": args, "ok": True}