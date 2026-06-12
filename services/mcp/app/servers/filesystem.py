"""filesystem MCP server stub (skeleton phase).

The real implementation is the responsibility of the filesystem
subagent (task 3.1) — it will expose 4 tools (``read_file`` /
``write_file`` / ``list_dir`` / ``search``) under the ``mcp[cli]``
stdio protocol. This stub provides the **one** thing the router
needs in the skeleton phase: a callable it can invoke when a
``fs_*`` tool name arrives, so end-to-end JSON-RPC plumbing can be
exercised.

The stub intentionally does **no** I/O. It returns a fixed
``{"server": "filesystem", "tool": ..., "ok": True}`` payload so the
test suite can assert that dispatch + audit + response shaping all
work without depending on the filesystem at all.
"""

from __future__ import annotations

from typing import Any

__all__ = ["HANDLER", "TOOL_NAMES"]


# Single advertised stub tool — replaced by 4 real tools when the
# subagent lands.
TOOL_NAMES: tuple[str, ...] = ("fs_stub",)


def HANDLER(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Skeleton-phase stub handler for filesystem tools.

    The real handler will validate ``args`` against the tool's JSON
    schema, run ``McpSecurityPolicy().check_path(args["path"])``,
    then do the I/O. For now it just echoes its inputs back so the
    router's dispatch / audit / response-shape logic can be tested
    in isolation.
    """
    return {"server": "filesystem", "tool": tool_name, "args": args, "ok": True}