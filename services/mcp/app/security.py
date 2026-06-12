"""Security policy for MCP servers (skeleton — extended by security worktree).

This module is the central allowlist/SSRF gate shared by every
``services/mcp/servers/*.py`` module. The fetch subagent imports
``McpSecurityPolicy`` and the three error classes from here; the
security worktree owns the full path-validation logic in
``McpSecurityPolicy.check_path``.

The three exception classes below are the *only* security-failure
surface a tool may raise — server code MUST NOT invent new exception
types for allowlist / SSRF violations.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlparse

__all__ = [
    "McpSecurityError",
    "McpResponseTooLargeError",
    "McpParseError",
    "McpSecurityPolicy",
]


class McpSecurityError(Exception):
    """Raised when a URL / path violates the allowlist or SSRF rules.

    The fetch server maps this to a structured ``error_class`` of
    ``"security"`` in the MCP error response.
    """


class McpResponseTooLargeError(Exception):
    """Raised when an upstream response exceeds ``MCP_FETCH_MAX_BYTES``.

    The fetch server maps this to a structured ``error_class`` of
    ``"runtime"`` in the MCP error response.
    """


class McpParseError(Exception):
    """Raised when the upstream payload cannot be decoded into the
    requested format (e.g. ``fetch_json`` against an HTML page).

    The fetch server maps this to a structured ``error_class`` of
    ``"runtime"`` in the MCP error response.
    """


class McpSecurityPolicy:
    """Env-driven URL/path allowlist + SSRF defense.

    The security worktree owns the canonical implementation; this
    minimal version exposes only the ``check_url`` surface the fetch
    server requires (Domain allowlist + private-IP rejection). It
    keeps the same public name so the security worktree can extend
    it without breaking the import contract.
    """

    def __init__(
        self,
        allowed_domains: list[str],
        max_response_bytes: int = 1_048_576,
    ) -> None:
        if not allowed_domains:
            raise McpSecurityError(
                "MCP_FETCH_ALLOWED_DOMAINS must be configured (no allow-all)"
            )
        self._allowed_domains = [d.lower() for d in allowed_domains]
        self._max_response_bytes = max_response_bytes

    @classmethod
    def from_env(cls) -> "McpSecurityPolicy":
        """Build a policy instance from the required env variables.

        Reads ``MCP_FETCH_ALLOWED_DOMAINS`` (comma-separated host list)
        and ``MCP_FETCH_MAX_BYTES`` (default 1 048 576 = 1 MiB).
        """
        raw_domains = os.environ.get("MCP_FETCH_ALLOWED_DOMAINS", "")
        max_bytes_raw = os.environ.get("MCP_FETCH_MAX_BYTES", "1048576")
        domains = [d.strip().lower() for d in raw_domains.split(",") if d.strip()]
        try:
            max_bytes = int(max_bytes_raw)
        except ValueError as exc:
            raise McpSecurityError(
                f"MCP_FETCH_MAX_BYTES must be an integer, got {max_bytes_raw!r}"
            ) from exc
        return cls(allowed_domains=domains, max_response_bytes=max_bytes)

    @property
    def max_response_bytes(self) -> int:
        return self._max_response_bytes

    def check_url(self, url: str) -> None:
        """Validate ``url`` against the allowlist + private-IP rules.

        Raises:
            McpSecurityError: when the URL is malformed, its host is
                not in the configured allowlist, or the host resolves
                to a private / loopback / link-local address.
        """
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise McpSecurityError(
                f"scheme {parsed.scheme!r} not allowed (must be http/https)"
            )
        host = parsed.hostname
        if not host:
            raise McpSecurityError(f"URL has no host: {url!r}")

        host_lower = host.lower()
        if not any(
            host_lower == d or host_lower.endswith("." + d)
            for d in self._allowed_domains
        ):
            raise McpSecurityError(
                f"host {host!r} not in MCP_FETCH_ALLOWED_DOMAINS allowlist"
            )

        # SSRF defense: refuse hosts that resolve to private/loopback/link-local IPs.
        try:
            # getaddrinfo can return both IPv4 and IPv6 records.
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror as exc:
            raise McpSecurityError(f"DNS resolution failed for {host!r}: {exc}") from exc
        for info in infos:
            sockaddr = info[4]
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            if self._is_forbidden_ip(ip):
                raise McpSecurityError(
                    f"host {host!r} resolves to forbidden IP {ip_str}"
                )

    @staticmethod
    def _is_forbidden_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        """Return ``True`` for private / loopback / link-local / multicast."""
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )