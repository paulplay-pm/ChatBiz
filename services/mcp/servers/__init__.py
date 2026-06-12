"""Compatibility package for older tests/imports.

The canonical implementation lives under ``app.servers``.  The
filesystem-server subagent originally imported ``servers.filesystem``;
keep this shim so both paths work.
"""
from app.servers import filesystem, fetch, postgres

__all__ = ["filesystem", "fetch", "postgres"]
