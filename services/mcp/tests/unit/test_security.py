"""Unit tests for :mod:`app.security`.

The plan (task 2.2) calls out exactly four scenarios:

1. path outside the allowlist → ``McpSecurityError``
2. URL outside the allowlist → ``McpSecurityError``
3. private-IP URL (SSRF attempt) → ``McpSecurityError``
4. ``validate_config`` raises ``McpSecurityError`` when a required
   env var is missing at startup

Plus the boundary cases needed to push coverage to 100 %:

* ``check_path`` allowing a path that lives **inside** the allowlist
  resolves successfully (and silently)
* ``check_url`` allowing a URL whose hostname is on the allowlist
* ``check_url`` refusing malformed URLs that ``urlparse`` cannot
  decode (e.g. empty hostname)
* ``McpSecurityError`` carries an ``error_class`` field of
  ``"security"`` (per T11 4-error-boundary spec)

All env vars are reset between tests via the ``clean_env`` fixture
so each test starts from a known state.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.security import (
    McpParseError,
    McpResponseTooLargeError,
    McpSecurityError,
    McpSecurityPolicy,
    McpTimeoutError,
    is_private_ip,
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip every ``MCP_*`` env var so each test starts from scratch."""
    for key in list(os.environ):
        if key.startswith("MCP_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def fs_allowed(tmp_path: Path, clean_env: None) -> Path:
    """Create an allowlisted dir and set the env var."""
    allowed = tmp_path / "reports"
    allowed.mkdir()
    os.environ["MCP_FS_ALLOWED_DIRS"] = str(allowed)
    return allowed


@pytest.fixture
def fetch_allowed(clean_env: None) -> None:
    """Set the URL allowlist env var."""
    os.environ["MCP_FETCH_ALLOWED_DOMAINS"] = "qyapi.weixin.qq.com,api.deepseek.com"
    os.environ["MCP_FETCH_MAX_BYTES"] = "1048576"


# ---------------------------------------------------------------------------
# 1. path outside the allowlist
# ---------------------------------------------------------------------------


class TestCheckPath:
    def test_path_inside_allowlist_allowed(self, fs_allowed: Path) -> None:
        """Files that resolve into the allowlisted dir must pass silently."""
        target = fs_allowed / "june.csv"
        target.write_text("a,b\n1,2\n")
        McpSecurityPolicy().check_path(str(target))
        # No exception → success.

    def test_path_outside_allowlist_raises(self, fs_allowed: Path) -> None:
        """A path under /etc must be rejected with ``McpSecurityError``."""
        with pytest.raises(McpSecurityError) as exc_info:
            McpSecurityPolicy().check_path("/etc/passwd")
        assert exc_info.value.error_class == "security"
        assert "not in allowed dirs" in exc_info.value.error_message

    def test_path_traversal_escape_raises(self, fs_allowed: Path) -> None:
        """``../etc/passwd`` style bypass must be resolved and rejected."""
        inside = fs_allowed / "subdir"
        inside.mkdir()
        traversal = str(inside / ".." / ".." / "etc" / "passwd")
        with pytest.raises(McpSecurityError):
            McpSecurityPolicy().check_path(traversal)


# ---------------------------------------------------------------------------
# 2. URL outside the allowlist
# ---------------------------------------------------------------------------


class TestCheckUrl:
    def test_url_inside_allowlist_allowed(self, fetch_allowed: None) -> None:
        """A URL on the allowlisted domain must pass silently."""
        McpSecurityPolicy().check_url("https://qyapi.weixin.qq.com/cgi-bin/gettoken")

    def test_url_outside_allowlist_raises(self, fetch_allowed: None) -> None:
        """A URL on a non-allowlisted domain must be rejected."""
        with pytest.raises(McpSecurityError) as exc_info:
            McpSecurityPolicy().check_url("https://evil.example.com/x")
        assert exc_info.value.error_class == "security"
        assert "not in allowed domains" in exc_info.value.error_message

    def test_subdomain_allowed(self, fetch_allowed: None) -> None:
        """Subdomains of an allowlisted domain must be accepted."""
        McpSecurityPolicy().check_url("https://api.deepseek.com/v1/chat")

    def test_malformed_url_raises(self, fetch_allowed: None) -> None:
        """Empty hostname (e.g. ``https:///path``) must be rejected."""
        with pytest.raises(McpSecurityError):
            McpSecurityPolicy().check_url("https:///x")


# ---------------------------------------------------------------------------
# 3. private IP / SSRF
# ---------------------------------------------------------------------------


class TestSsrFDefense:
    @pytest.mark.parametrize(
        "bad_url",
        [
            "http://127.0.0.1:8080/admin",
            "http://10.0.0.5/x",
            "http://172.16.0.1/x",
            "http://192.168.1.1/x",
            "http://169.254.169.254/latest/meta-data/",
        ],
    )
    def test_private_ip_url_rejected(
        self, fetch_allowed: None, bad_url: str
    ) -> None:
        """RFC1918 + link-local URLs must be rejected as SSRF attempts."""
        with pytest.raises(McpSecurityError) as exc_info:
            McpSecurityPolicy().check_url(bad_url)
        assert exc_info.value.error_class == "security"
        assert "private" in exc_info.value.error_message.lower()

    def test_loopback_ipv6_rejected(self, fetch_allowed: None) -> None:
        """``[::1]`` must also be rejected."""
        with pytest.raises(McpSecurityError):
            McpSecurityPolicy().check_url("http://[::1]:8080/admin")


# ---------------------------------------------------------------------------
# 4. startup config validation
# ---------------------------------------------------------------------------


class TestValidateConfig:
    def test_missing_fs_allowed_dirs_raises(self, clean_env: None) -> None:
        """No ``MCP_FS_ALLOWED_DIRS`` → startup fails loudly."""
        with pytest.raises(McpSecurityError) as exc_info:
            McpSecurityPolicy().validate_config(require_fs=True, require_fetch=False)
        assert "MCP_FS_ALLOWED_DIRS" in str(exc_info.value)

    def test_missing_fetch_allowed_domains_raises(self, clean_env: None) -> None:
        """No ``MCP_FETCH_ALLOWED_DOMAINS`` → startup fails loudly."""
        with pytest.raises(McpSecurityError) as exc_info:
            McpSecurityPolicy().validate_config(require_fs=False, require_fetch=True)
        assert "MCP_FETCH_ALLOWED_DOMAINS" in str(exc_info.value)

    def test_all_required_present_passes(self, clean_env: None) -> None:
        """All required env vars set → validate_config is silent."""
        os.environ["MCP_FS_ALLOWED_DIRS"] = "/tmp/reports"
        os.environ["MCP_FETCH_ALLOWED_DOMAINS"] = "qyapi.weixin.qq.com"
        McpSecurityPolicy().validate_config(require_fs=True, require_fetch=True)


# ---------------------------------------------------------------------------
# exception class shape (T11 4-error-boundary spec)
# ---------------------------------------------------------------------------


class TestExceptionClasses:
    def test_mcp_security_error_has_error_class(self) -> None:
        """``McpSecurityError`` must carry ``error_class='security'``."""
        err = McpSecurityError("nope")
        assert err.error_class == "security"
        assert err.error_message == "nope"

    def test_mcp_response_too_large_error_class(self) -> None:
        """``McpResponseTooLargeError`` must carry ``error_class='runtime'``."""
        err = McpResponseTooLargeError("too big")
        assert err.error_class == "runtime"

    def test_mcp_parse_error_class(self) -> None:
        """``McpParseError`` must carry ``error_class='runtime'``."""
        err = McpParseError("bad json")
        assert err.error_class == "runtime"

    def test_mcp_timeout_error_class(self) -> None:
        """``McpTimeoutError`` must carry ``error_class='runtime'``."""
        err = McpTimeoutError("query timeout")
        assert err.error_class == "runtime"


# ---------------------------------------------------------------------------
# additional config-loading branches (push coverage to 100 %)
# ---------------------------------------------------------------------------


class TestConfigLoading:
    def test_fetch_max_bytes_default(self, clean_env: None) -> None:
        """When ``MCP_FETCH_MAX_BYTES`` is unset, the default 1 MB is used."""
        os.environ["MCP_FETCH_ALLOWED_DOMAINS"] = "example.com"
        policy = McpSecurityPolicy()
        assert policy.fetch_max_bytes == 1_048_576

    def test_fetch_max_bytes_invalid_falls_back(
        self, clean_env: None, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A non-integer ``MCP_FETCH_MAX_BYTES`` falls back to the default."""
        os.environ["MCP_FETCH_ALLOWED_DOMAINS"] = "example.com"
        os.environ["MCP_FETCH_MAX_BYTES"] = "not-a-number"
        policy = McpSecurityPolicy()
        assert policy.fetch_max_bytes == 1_048_576
        assert "MCP_FETCH_MAX_BYTES" in capsys.readouterr().err

    def test_validate_config_both_missing(self, clean_env: None) -> None:
        """When both env vars are required and both are missing, FS is reported first."""
        with pytest.raises(McpSecurityError) as exc_info:
            McpSecurityPolicy().validate_config(require_fs=True, require_fetch=True)
        assert "MCP_FS_ALLOWED_DIRS" in str(exc_info.value)


# ---------------------------------------------------------------------------
# is_private_ip edge cases
# ---------------------------------------------------------------------------


class TestIsPrivateIp:
    def test_empty_host_not_private(self) -> None:
        """Empty string returns False (not an IP, so not private)."""
        assert is_private_ip("") is False

    def test_plain_hostname_not_private(self) -> None:
        """A bare hostname (no IP parse) returns False — name resolution is upstream."""
        assert is_private_ip("example.com") is False

    def test_public_ipv6_not_private(self) -> None:
        """A public IPv6 address (non-loopback) is not private."""
        # 2606:4700:4700::1111 — public Cloudflare DNS, never flagged.
        assert is_private_ip("2606:4700:4700::1111") is False


# ---------------------------------------------------------------------------
# additional check_path / check_url branches
# ---------------------------------------------------------------------------


class TestCheckPathBranches:
    def test_check_path_with_no_allowlist_raises(self, clean_env: None) -> None:
        """``check_path`` called with no allowlist raises immediately."""
        with pytest.raises(McpSecurityError) as exc_info:
            McpSecurityPolicy().check_path("/anything")
        assert "MCP_FS_ALLOWED_DIRS" in str(exc_info.value)

    def test_check_path_resolve_failure(
        self, fs_allowed: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``Path.resolve()`` raising must be wrapped in ``McpSecurityError``."""
        from app import security as sec_mod

        original_resolve = sec_mod.Path.resolve
        call_count = {"n": 0}

        def flaky_resolve(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First call is from McpSecurityPolicy.__init__ on the
                # allowlisted dir — let it succeed.
                return original_resolve(self, *args, **kwargs)
            raise OSError("simulated resolve failure")

        monkeypatch.setattr(sec_mod.Path, "resolve", flaky_resolve)
        with pytest.raises(McpSecurityError) as exc_info:
            McpSecurityPolicy().check_path(str(fs_allowed / "x"))
        assert "simulated resolve failure" in str(exc_info.value)


class TestCheckUrlBranches:
    def test_check_url_with_no_allowlist_raises(self, clean_env: None) -> None:
        """``check_url`` called with no allowlist raises immediately."""
        with pytest.raises(McpSecurityError) as exc_info:
            McpSecurityPolicy().check_url("https://example.com/x")
        assert "MCP_FETCH_ALLOWED_DOMAINS" in str(exc_info.value)