"""fetch MCP server placeholder (skeleton phase).

Implemented by the fetch subagent (task 4.1). Will expose 3 tools
(``fetch_url`` / ``fetch_html`` / ``fetch_json``) under the
``mcp[cli]`` stdio protocol, with URL allowlist + SSRF defense via
:class:`app.security.McpSecurityPolicy`.
"""

from __future__ import annotations

__all__: list[str] = []