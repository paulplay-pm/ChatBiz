"""NGINX L4 LB config test — verifies deploy/audit-and-isolation/nginx.conf.

Per task 2.3 of `openspec/changes/gateway-egress-enforcement-p0/`. Uses
`nginx -t` (plan.md's stated validator) if available on PATH to do a
real syntax check; falls back to structural assertions otherwise.

The structural checks cover the spec's literal requirements
(`health_check`-style semantics via `max_fails`/`fail_timeout`):
2 upstream servers, fail_timeout ≤ 30s, listen port 8080, etc.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]  # tests/unit/ -> tests/ -> audit-and-isolation/ -> services/ -> repo
NGINX_CONF = REPO_ROOT / "deploy" / "audit-and-isolation" / "nginx.conf"


# ----- file presence --------------------------------------------------------

def test_nginx_conf_file_exists() -> None:
    assert NGINX_CONF.is_file(), f"missing {NGINX_CONF}"


def test_nginx_conf_is_non_empty() -> None:
    assert NGINX_CONF.stat().st_size > 0


# ----- spec-literal requirements -------------------------------------------

def test_has_stream_block() -> None:
    """L4 LB must use the `stream` block (TCP-level), not http (L7).

    The `stream` block sits at top level, parallel to `http`. It allows
    raw TCP load balancing without HTTP parsing, which is what we want
    for an LLM streaming gateway.
    """
    content = NGINX_CONF.read_text()
    assert re.search(r"^\s*stream\s*\{", content, re.MULTILINE), (
        "missing top-level stream {} block (L4 LB requires it)"
    )


def test_has_upstream_block_named_audit_and_isolation() -> None:
    content = NGINX_CONF.read_text()
    assert re.search(
        r"upstream\s+audit_and_isolation_upstream\s*\{", content
    ), "upstream block 'audit_and_isolation_upstream' not found"


def test_upstream_has_two_servers() -> None:
    """2 replicas (task 2.2) → 2 upstream server entries.

    Both point at the K8s Service DNS name (chatbiz-audit-and-isolation)
    which round-robins across the 2 pods. The conf file uses the same
    Service name twice with two distinct connection pools.
    """
    content = NGINX_CONF.read_text()
    # Find the upstream block body
    m = re.search(
        r"upstream\s+audit_and_isolation_upstream\s*\{(.*?)\}",
        content,
        re.DOTALL,
    )
    assert m, "upstream block not found"
    body = m.group(1)
    server_lines = [
        line for line in body.splitlines()
        if re.match(r"\s*server\s+\S+", line)
    ]
    assert len(server_lines) == 2, (
        f"expected 2 upstream server entries (one per replica), got {len(server_lines)}: {server_lines}"
    )


def test_upstream_uses_max_fails_and_fail_timeout() -> None:
    """Spec's `health_check fails=2 passes=1 interval=5s` is NGINX Plus
    syntax. Opensource NGINX approximates it with `max_fails=2` +
    `fail_timeout`. We assert both directives are present on every server
    line, with `max_fails=2` matching the spec's `fails=2`."""
    content = NGINX_CONF.read_text()
    m = re.search(
        r"upstream\s+audit_and_isolation_upstream\s*\{(.*?)\}",
        content,
        re.DOTALL,
    )
    assert m
    body = m.group(1)
    server_lines = [
        line for line in body.splitlines()
        if re.match(r"\s*server\s+\S+", line)
    ]
    for line in server_lines:
        assert "max_fails=2" in line, f"server line missing max_fails=2: {line}"
        assert "fail_timeout=" in line, f"server line missing fail_timeout: {line}"


def test_fail_timeout_meets_interval_spec() -> None:
    """Spec: `health_check interval=5s` ⇒ fail_timeout should be ≤ 30s
    (we use 10s, which gives ~5s effective probe cadence via repeated
    proxy_connect attempts during the 10s window)."""
    content = NGINX_CONF.read_text()
    matches = re.findall(r"fail_timeout=(\d+)s", content)
    assert matches, "no fail_timeout directive found"
    for ft in matches:
        seconds = int(ft)
        assert seconds <= 30, (
            f"fail_timeout={seconds}s should be ≤ 30s to maintain reasonable "
            f"failover latency (spec interval=5s)"
        )


def test_server_listens_on_port_8080() -> None:
    """LB exposes the gateway on port 8080 (same as the gateway itself).
    Clients always hit 8080, NGINX routes to one of the 2 upstream pods."""
    content = NGINX_CONF.read_text()
    assert re.search(r"listen\s+8080\s*;", content), (
        "server block missing 'listen 8080;' directive"
    )


def test_proxy_timeout_is_30s() -> None:
    """Spec literal: `proxy_timeout 30s`."""
    content = NGINX_CONF.read_text()
    assert re.search(r"proxy_timeout\s+30s\s*;", content), (
        "server block missing 'proxy_timeout 30s;' (spec requirement)"
    )


def test_proxy_pass_references_upstream() -> None:
    content = NGINX_CONF.read_text()
    assert re.search(
        r"proxy_pass\s+audit_and_isolation_upstream\s*;", content
    ), "proxy_pass must reference audit_and_isolation_upstream"


def test_has_failover_directives() -> None:
    """On upstream failure, NGINX should try the other upstream.
    `proxy_next_upstream on` is the standard failover primitive."""
    content = NGINX_CONF.read_text()
    assert "proxy_next_upstream on" in content or "proxy_next_upstream on;" in content


def test_has_proxy_connect_timeout() -> None:
    """Without a connect timeout, a dead upstream could hold client
    connections open for the full 30s proxy_timeout. 2s connect timeout
    fails fast and lets the failover path kick in quickly."""
    content = NGINX_CONF.read_text()
    assert re.search(
        r"proxy_connect_timeout\s+\d+s\s*;", content
    ), "no proxy_connect_timeout — dead upstreams would hold client connections"


# ----- L4 vs L7 sanity check -----------------------------------------------

def test_no_http_proxy_pass_in_stream_block() -> None:
    """The stream block must not contain `proxy_pass http://` (which would
    imply L7 routing). L4 LB uses bare `proxy_pass <upstream_name>`."""
    content = NGINX_CONF.read_text()
    m = re.search(r"stream\s*\{(.*?)\n\}", content, re.DOTALL)
    assert m
    stream_body = m.group(1)
    assert "proxy_pass http://" not in stream_body, (
        "stream block contains L7 proxy_pass http:// — should be L4 "
        "with bare upstream name"
    )


# ----- nginx -t optional runner --------------------------------------------

@pytest.mark.skipif(
    shutil.which("nginx") is None,
    reason="nginx not installed locally; CI runs nginx -t in the static-scan workflow",
)
def test_nginx_t_validates_config() -> None:
    """If nginx is on PATH, run `nginx -t -c <our conf>` to verify syntax.

    The conf file references a PID file path and a few log paths; for
    the test, override them via -g directives so the validation doesn't
    try to write to /var/run/nginx.pid in a non-privileged environment.
    """
    result = subprocess.run(
        [
            "nginx",
            "-t",
            "-c", str(NGINX_CONF),
            "-g", "pid /tmp/nginx-test.pid; error_log /tmp/nginx-test-error.log;",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    # `nginx -t` exits 0 on success, non-zero (often 1) on syntax error.
    assert result.returncode == 0, (
        f"nginx -t failed (rc={result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
