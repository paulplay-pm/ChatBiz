"""MCP server implementations.

Each submodule is a standalone ``mcp[cli]`` server exposing a small
set of tools. They share no code beyond the security policy in
:mod:`app.security` and the audit-egress helper used by the router.
"""

__all__: list[str] = []