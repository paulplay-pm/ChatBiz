"""MCP server stubs (skeleton phase).

Each submodule exposes a ``HANDLER(tool_name, args) -> dict``
callable and a ``TOOL_NAMES`` tuple. The router imports these and
dispatches calls based on a ``tool_name`` prefix:

* ``fs_*``    → :mod:`app.servers.filesystem`
* ``fetch_*`` → :mod:`app.servers.fetch`
* ``pg_*``    → :mod:`app.servers.postgres`

The 3 subagents will replace the stub ``HANDLER``s with real
``mcp[cli]`` ``Server``-backed implementations (tasks 3.1 / 4.1 /
5.1). The router contract — ``HANDLER(tool_name, args) -> dict``
returning either a payload or raising one of the 4 ``McpError``
subclasses — does not change.
"""

from __future__ import annotations

# Re-export the 3 server modules so callers can write
# ``app.servers.fetch.HANDLER`` instead of ``app.servers.fetch``.
from app.servers import fetch
from app.servers import filesystem
from app.servers import postgres

__all__ = ["fetch", "filesystem", "postgres"]