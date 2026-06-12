"""Security policy for the ChatBiz MCP integration.

Three things live here:

1. The four :class:`McpError` subclasses the MCP tool layer raises.
   They each carry an ``error_class`` field so the router can map
   them onto T11's 4-error-boundary envelope
   (``security`` / ``runtime`` / ``user`` / ``canvas``). The four
   classes currently in use:

   * :class:`McpSecurityError` — ``error_class='security'``
   * :class:`McpResponseTooLargeError` — ``error_class='runtime'``
   * :class:`McpParseError` — ``error_class='runtime'``
   * :class:`McpTimeoutError` — ``error_class='runtime'``

2. :class:`McpSecurityPolicy` — the env-driven allowlist + SSRF
   defense the three servers consult before every tool call.

3. :func:`is_private_ip` — a small helper used by
   :meth:`McpSecurityPolicy.check_url` and by the fetch server's
   SSRF defense.

The policy is intentionally stateless after construction — every
method reads from the *current* environment so operators can flip
the allowlist without restarting, and tests can use ``monkeypatch``
to drive each scenario.

Per ``openspec/changes/mcp-server-integration-mvp/design.md`` (D6 /
D7 / D9 / R3):

* directory allowlist = ``MCP_FS_ALLOWED_DIRS`` (comma-separated)
  with ``Path.resolve()`` to defeat ``..`` traversal
* URL allowlist = ``MCP_FETCH_ALLOWED_DOMAINS`` (comma-separated)
  plus private-IP rejection for ``127.0.0.0/8``, ``10.0.0.0/8``,
  ``172.16.0.0/12``, ``192.168.0.0/16``, ``169.254.0.0/16`` and
  IPv6 ``::1``
* response size limit = ``MCP_FETCH_MAX_BYTES`` (default 1 MB)
"""

from __future__ import annotations

import ipaddress
import logging
import os
import socket  # imported so that patchers like _DNSGuard work
import sys
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# error classes — T11 4-error-boundary spec
# ---------------------------------------------------------------------------


class McpError(Exception):
    """Base for all MCP-raised errors.

    Subclasses override :attr:`error_class` so the router can build
    the correct ``{error_class, error_message, trace_id}`` envelope
    that T11 mandates.
    """

    error_class: str = "runtime"
    error_message: str = ""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.error_message = message


class McpSecurityError(McpError):
    """Caller asked for a resource the policy forbids.

    Used for: path-traversal escape, URL on a non-allowlisted domain,
    private-IP SSRF attempt, missing required env var at startup.
    """

    error_class = "security"


class McpResponseTooLargeError(McpError):
    """Upstream response exceeded the configured byte budget."""

    error_class = "runtime"


class McpParseError(McpError):
    """Upstream returned bytes the parser could not decode."""

    error_class = "runtime"


class McpTimeoutError(McpError):
    """A query exceeded its configured timeout."""

    error_class = "runtime"


# ---------------------------------------------------------------------------
# private-IP detection (SSRF defense)
# ---------------------------------------------------------------------------


# RFC1918 + loopback + link-local IPv4 ranges, plus the IPv6 loopback.
# Anything matching one of these is treated as "the public internet
# cannot route here" and rejected outright.
_PRIVATE_IPV4_NETWORKS: tuple[ipaddress.IPv4Network, ...] = (
    ipaddress.IPv4Network("127.0.0.0/8"),
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
    ipaddress.IPv4Network("169.254.0.0/16"),
)


def is_private_ip(host: str) -> bool:
    """Return ``True`` when ``host`` resolves to a private/loopback address.

    Accepts either a bare IP literal (``127.0.0.1``) or a bracketed
    IPv6 literal (``[::1]``). Returns ``False`` for plain hostnames —
    name resolution is intentionally NOT performed here; the
    allowlist is applied first, and DNS rebinding is mitigated by
    resolving again inside the fetch client.
    """
    if not host:
        return False
    candidate = host.strip("[]")
    try:
        addr = ipaddress.ip_address(candidate)
    except ValueError:
        return False
    if isinstance(addr, ipaddress.IPv6Address) and addr.is_loopback:
        return True
    if isinstance(addr, ipaddress.IPv4Address):
        return any(addr in net for net in _PRIVATE_IPV4_NETWORKS)
    return False


# ---------------------------------------------------------------------------
# env parsing helpers
# ---------------------------------------------------------------------------


def _split_csv(value: str) -> list[str]:
    """Split a comma-separated env var, dropping blanks."""
    return [item.strip() for item in value.split(",") if item.strip()]


def _int_env(name: str, default: int) -> int:
    """Read an int from the environment with a logged fallback."""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning(
            "MCP env %s=%r is not an integer; falling back to %d", name, raw, default
        )
        # Mirror to stderr so the warning surfaces in container logs
        # even when logging is unconfigured at startup.
        print(
            f"warning: MCP env {name}={raw!r} is not an integer;"
            f" falling back to {default}",
            file=sys.stderr,
        )
        return default


# ---------------------------------------------------------------------------
# the policy itself
# ---------------------------------------------------------------------------


DEFAULT_FETCH_MAX_BYTES = 1_048_576  # 1 MiB


class McpSecurityPolicy:
    """Env-driven allowlist + SSRF defense shared by the 3 servers.

    Construction is cheap — it just snapshots the current
    environment into instance attributes so tests can introspect
    ``policy.fetch_max_bytes`` etc. without re-parsing the env on
    every call.
    """

    DEFAULT_FETCH_MAX_BYTES = 1_048_576  # 1 MiB

    def __init__(
        self,
        *,
        allowed_dirs: tuple[Path, ...] | list[Path] | None = None,
        allowed_domains: tuple[str, ...] | list[str] | None = None,
        max_response_bytes: int | None = None,
    ) -> None:
        self.fs_allowed_dirs: tuple[Path, ...] = (
            tuple(Path(p).resolve() for p in allowed_dirs)
            if allowed_dirs is not None
            else tuple(
                Path(p).resolve()
                for p in _split_csv(os.environ.get("MCP_FS_ALLOWED_DIRS", ""))
            )
        )
        self.fetch_allowed_domains: tuple[str, ...] = (
            tuple(allowed_domains)
            if allowed_domains is not None
            else tuple(_split_csv(os.environ.get("MCP_FETCH_ALLOWED_DOMAINS", "")))
        )
        self.fetch_max_bytes: int = (
            max_response_bytes
            if max_response_bytes is not None
            else _int_env("MCP_FETCH_MAX_BYTES", self.DEFAULT_FETCH_MAX_BYTES)
        )
        self.max_response_bytes = self.fetch_max_bytes  # alias for fetch server compat

    # -- construction helpers ------------------------------------------------

    @classmethod
    def from_env(cls, *, require_fs: bool = False, require_fetch: bool = False) -> "McpSecurityPolicy":
        """Construct a policy from the current process environment.

        Server implementations call this at startup to build a policy
        instance. When *require_fs* or *require_fetch* are True the
        helper also calls :meth:`validate_config` so that a missing
        mandatory env var raises immediately (vs failing at the first
        tool call).
        """
        policy = cls()
        if require_fs or require_fetch:
            policy.validate_config(require_fs=require_fs, require_fetch=require_fetch)
        return policy

    # -- public API ----------------------------------------------------------

    def validate_config(
        self,
        *,
        require_fs: bool = False,
        require_fetch: bool = False,
    ) -> None:
        """Fail-loud check that the required env vars are populated.

        Each server invokes this at startup with only the flags
        that apply to itself (filesystem server → ``require_fs=True``;
        fetch server → ``require_fetch=True``). We deliberately do
        NOT default both to ``True`` — that way the three servers
        can boot independently with different env vars present.
        """
        if require_fs and not self.fs_allowed_dirs:
            raise McpSecurityError(
                "MCP_FS_ALLOWED_DIRS is not configured (filesystem server "
                "refuses to start without an explicit allowlist)"
            )
        if require_fetch and not self.fetch_allowed_domains:
            raise McpSecurityError(
                "MCP_FETCH_ALLOWED_DOMAINS is not configured (fetch server "
                "refuses to start without an explicit allowlist)"
            )

    def check_path(self, path: str) -> Path:
        """Return the resolved path if it is inside ``MCP_FS_ALLOWED_DIRS``.

        ``Path.resolve()`` walks the full chain of ``..`` segments
        *and* follows symlinks, so traversal/escape attempts land on
        the real on-disk path before we compare it to the allowlist.
        """
        if not self.fs_allowed_dirs:
            raise McpSecurityError(
                "MCP_FS_ALLOWED_DIRS is not configured (refusing any path)"
            )
        try:
            resolved = Path(path).resolve()
        except (OSError, RuntimeError) as exc:
            raise McpSecurityError(f"cannot resolve path {path!r}: {exc}") from exc
        if not any(self._is_within(resolved, allowed) for allowed in self.fs_allowed_dirs):
            raise McpSecurityError(
                f"path {resolved} is not in allowed dirs {self.fs_allowed_dirs}"
            )
        return resolved

    def check_url(self, url: str) -> None:
        """Reject URLs whose host is off the allowlist or a private IP."""
        if not self.fetch_allowed_domains:
            raise McpSecurityError(
                "MCP_FETCH_ALLOWED_DOMAINS is not configured (refusing any URL)"
            )
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if not host:
            raise McpSecurityError(f"URL {url!r} has no hostname")
        if is_private_ip(host):
            raise McpSecurityError(
                f"URL {url!r} targets a private IP (SSRF defense)"
            )
        if not self._host_allowed(host):
            raise McpSecurityError(
                f"URL {url!r} host {host!r} is not in allowed domains"
                f" {self.fetch_allowed_domains}"
            )

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _is_within(candidate: Path, root: Path) -> bool:
        """Return True iff ``candidate`` is the same as or below ``root``."""
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            return False

    def _host_allowed(self, host: str) -> bool:
        """Match the host (or any of its parent labels) against the allowlist."""
        host = host.lower()
        for allowed in self.fetch_allowed_domains:
            allowed = allowed.lower()
            if host == allowed or host.endswith("." + allowed):
                return True
        return False


__all__ = [
    "DEFAULT_FETCH_MAX_BYTES",
    "McpError",
    "McpParseError",
    "McpResponseTooLargeError",
    "McpSecurityError",
    "McpSecurityPolicy",
    "McpTimeoutError",
    "is_private_ip",
]