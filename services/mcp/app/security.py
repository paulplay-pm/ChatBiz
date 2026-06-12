"""Stub security module for the filesystem-server worktree.

The skeleton worktree owns the real ``McpSecurityPolicy``. This stub
exists only so that the filesystem server's tests can run in
isolation. When the skeleton worktree merges, it will overwrite this
file with the full implementation; the public symbols
(``McpSecurityError``, ``McpSecurityPolicy``) are contractually stable
per ``openspec/changes/mcp-server-integration-mvp/design.md`` D9.
"""

from __future__ import annotations

from pathlib import Path


class McpSecurityError(Exception):
    """Raised when an MCP tool call violates the security policy.

    Carries a stable error class so callers can branch on the category
    without parsing strings (e.g. ``{"error_class": "security", ...}``
    in the spec).
    """

    error_class = "security"

    def __init__(self, message: str):
        super().__init__(message)
        self.error_message = message


class McpSecurityPolicy:
    """Minimal filesystem-side policy.

    Full implementation (URL allowlist + SSRF, postgres read-only user,
    etc.) lives in the skeleton worktree. The methods here are the
    subset that ``servers/filesystem.py`` needs.
    """

    def __init__(self, allowed_dirs: list[Path]):
        self._allowed = [Path(d).resolve() for d in allowed_dirs]

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "McpSecurityPolicy":
        env = env if env is not None else dict(__import__("os").environ)
        raw = env.get("MCP_FS_ALLOWED_DIRS", "")
        if not raw.strip():
            raise McpSecurityError(
                "MCP_FS_ALLOWED_DIRS env var is required (no whitelist = no service)"
            )
        dirs = [Path(p.strip()) for p in raw.split(",") if p.strip()]
        if not dirs:
            raise McpSecurityError(
                "MCP_FS_ALLOWED_DIRS env var is empty (no whitelist = no service)"
            )
        return cls(dirs)

    def check_path(self, path: str | Path) -> Path:
        """Resolve ``path`` and verify it is inside one of the allowed
        dirs. Returns the resolved path on success.

        Raises ``McpSecurityError`` if the resolved path escapes the
        whitelist (e.g. ``../`` traversal, symlink pointing outside,
        absolute path outside).
        """
        try:
            resolved = Path(path).resolve(strict=False)
        except (OSError, RuntimeError, ValueError) as e:
            raise McpSecurityError(f"path resolution failed: {e}") from e

        for allowed in self._allowed:
            try:
                resolved.relative_to(allowed)
                return resolved
            except ValueError:
                continue

        raise McpSecurityError(
            f"path not in allowed dirs: {resolved} not under any of "
            f"{[str(d) for d in self._allowed]}"
        )


__all__ = ["McpSecurityError", "McpSecurityPolicy"]
