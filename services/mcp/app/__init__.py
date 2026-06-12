"""ChatBiz MCP server integration package.

Layout (per ``openspec/changes/mcp-server-integration-mvp/design.md``):

* ``app.security`` — :class:`McpSecurityPolicy` env-driven allowlist + SSRF defense
* ``app.router`` — :class:`McpRouter` stdio JSON-RPC dispatch to 3 servers
* ``app.servers.filesystem`` — filesystem MCP server (4 tools)
* ``app.servers.fetch`` — fetch MCP server (3 tools)
* ``app.servers.postgres`` — postgres MCP server (3 tools)

Every server registers its tools through the ``mcp[cli]`` library and
delegates every external call through
``services/audit-and-isolation/app/llm/client.py`` (eng-review
decision #1 — egress enforcement).
"""

__all__: list[str] = []