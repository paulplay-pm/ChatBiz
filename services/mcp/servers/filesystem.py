"""Compatibility re-export for ``app.servers.filesystem``.

This proxy re-exports *every* public attribute of the real module
so that older test code (which uses ``from servers import filesystem``
and expects ``filesystem.asyncio``, ``filesystem.stdio_server``,
etc.) works without rewriting.
"""
import app.servers.filesystem as _mod

# Re-export everything the real module exposes.
from app.servers.filesystem import *  # noqa: F403, E402

# Cherry-pick the attributes that the tests reach for but that
# are not re-exported via __all__ (e.g. framework imports).
for _name in ("asyncio", "stdio_server", "mcp", "httpx", "McpSecurityError", "McpSecurityPolicy"):
    if hasattr(_mod, _name):
        globals()[_name] = getattr(_mod, _name)
