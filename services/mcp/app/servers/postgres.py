"""postgres MCP server placeholder (skeleton phase).

Implemented by the postgres subagent (task 5.1). Will expose 3
read-only tools (``execute_query`` / ``list_tables`` /
``describe_table``) under the ``mcp[cli]`` stdio protocol, using
the dedicated read-only PG user and ``SET TRANSACTION READ ONLY``.
"""

from __future__ import annotations

__all__: list[str] = []