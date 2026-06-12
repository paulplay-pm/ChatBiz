"""filesystem MCP server placeholder (skeleton phase).

Implemented by the filesystem subagent (task 3.1). Will expose 4
tools (``read_file`` / ``write_file`` / ``list_dir`` / ``search``)
under the ``mcp[cli]`` stdio protocol, with directory allowlist
enforcement via :class:`app.security.McpSecurityPolicy`.
"""

from __future__ import annotations

__all__: list[str] = []