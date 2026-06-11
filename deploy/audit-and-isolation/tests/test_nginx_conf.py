"""Tests for the audit-and-isolation NGINX stream L4 LB config.

Two layers of validation:

1. **Textual contract** — parse the ``stream { ... }`` block and
   assert structural elements: 2 upstream servers, health_check,
   proxy_timeout 30s, listen 8080, proxy_pass upstream name.
2. **nginx -t integration** — if nginx is on PATH, run a real syntax
   check against the config; otherwise skip.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

CONF = Path(__file__).resolve().parent.parent / "nginx.conf"


def _read() -> str:
    return CONF.read_text()


def test_config_has_stream_block():
    body = _read()
    assert re.search(r"^\s*stream\s*\{", body, re.MULTILINE), "missing 'stream' block"


def test_upstream_block_has_two_servers():
    """The HA spec mandates 2 active-active instances."""
    body = _read()
    m = re.search(r"upstream\s+(\w+)\s*\{([^}]*)\}", body, re.DOTALL)
    assert m, "missing upstream block"
    servers = re.findall(r"^\s*server\s+", m.group(2), re.MULTILINE)
    assert len(servers) == 2, f"expected 2 upstream servers, got {len(servers)}"


def test_upstream_uses_cluster_dns_or_ip():
    """Each upstream server must point at the audit-and-isolation backend."""
    body = _read()
    m = re.search(r"upstream\s+(\w+)\s*\{([^}]*)\}", body, re.DOTALL)
    assert m
    for line in m.group(2).splitlines():
        if line.strip().startswith("server "):
            assert ":8080" in line, f"upstream server missing :8080: {line!r}"


def test_server_block_listens_on_8080():
    body = _read()
    assert re.search(r"listen\s+8080\s*;", body), "missing 'listen 8080;'"


def test_server_block_proxies_to_upstream():
    body = _read()
    assert re.search(r"proxy_pass\s+audit_isolation\s*;", body), "missing proxy_pass audit_isolation;"


def test_health_check_5s_fails_2_passes_1():
    body = _read()
    m = re.search(r"health_check\s+([^;]+);", body)
    assert m, "missing health_check directive"
    args = m.group(1)
    assert "interval=5s" in args
    assert "fails=2" in args
    assert "passes=1" in args


def test_proxy_timeout_is_30s():
    body = _read()
    assert re.search(r"proxy_timeout\s+30s\s*;", body), "missing proxy_timeout 30s;"


@pytest.mark.skipif(shutil.which("nginx") is None, reason="nginx not on PATH")
def test_nginx_t_validates_config(tmp_path):
    """If nginx is installed, do a real syntax check."""
    # nginx -t requires a prefix; use a temp dir with stub log paths
    conf = _read().replace("/var/log/nginx/", str(tmp_path) + "/")
    conf_path = tmp_path / "nginx.conf"
    conf_path.write_text(conf)
    result = subprocess.run(
        ["nginx", "-t", "-c", str(conf_path), "-p", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"nginx -t failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
