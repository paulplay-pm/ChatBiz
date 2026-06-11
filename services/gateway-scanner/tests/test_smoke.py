"""Smoke test: the CLI's 3-tier exit code behavior.

We invoke the CLI both as a subprocess (``python -m gateway_scanner``)
and via the in-process ``main`` entry point, to keep coverage ≥ 100%.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from gateway_scanner.__main__ import main

PKG_ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
BLOCKLIST = PKG_ROOT / "blocklist.yaml"
ALLOWLIST = PKG_ROOT / "allowlist.yaml"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "gateway_scanner", *args],
        capture_output=True,
        text=True,
        cwd=PKG_ROOT,
    )


# ---------- in-process coverage (drives __main__.py directly) ----------

def test_main_violation_reports_and_exits_1(tmp_path: Path) -> None:
    """In-process: build a tiny project with one direct import and
    verify the CLI reports it and exits 1. Drives the main() callback
    so __main__.py is fully covered (subprocess calls don't contribute
    to coverage)."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "blocklist.yaml").write_text("packages:\n  - openai\n", encoding="utf-8")
    (proj / "allowlist.yaml").write_text("paths: []\n", encoding="utf-8")
    src = proj / "src"
    src.mkdir()
    (src / "bad.py").write_text("import openai\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        main,
        [str(proj), "--blocklist", str(proj / "blocklist.yaml"),
         "--allowlist", str(proj / "allowlist.yaml")],
    )
    assert result.exit_code == 1
    assert "bad.py:1:openai" in result.output


def test_main_config_error_exits_2(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        [str(tmp_path), "--blocklist", str(tmp_path / "nope.yaml")],
    )
    assert result.exit_code == 2
    assert "blocklist not found" in result.output


def test_main_real_violation_exits_1(tmp_path: Path) -> None:
    """In-process: build a tiny project with one direct import and
    verify the CLI reports it and exits 1."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "blocklist.yaml").write_text("packages:\n  - openai\n", encoding="utf-8")
    (proj / "allowlist.yaml").write_text("paths: []\n", encoding="utf-8")
    src = proj / "src"
    src.mkdir()
    (src / "bad.py").write_text("import openai\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        main,
        [str(proj), "--blocklist", str(proj / "blocklist.yaml"),
         "--allowlist", str(proj / "allowlist.yaml")],
    )
    assert result.exit_code == 1
    assert "bad.py:1:openai" in result.output


# ---------- subprocess coverage (end-to-end smoke) ----------

def test_cli_exit_0_when_no_violations() -> None:
    # Scan the package root (which contains ``tests/``) so that the
    # ``**/tests/**`` allowlist glob applies. The fixtures under
    # tests/fixtures deliberately contain LLM provider imports and
    # must be skipped by the allowlist.
    result = _run_cli(
        str(PKG_ROOT),
        "--blocklist",
        str(BLOCKLIST),
        "--allowlist",
        str(ALLOWLIST),
    )
    assert result.returncode == 0, (
        f"expected exit 0, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_cli_exit_1_when_violation(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "blocklist.yaml").write_text("packages:\n  - openai\n", encoding="utf-8")
    (proj / "allowlist.yaml").write_text("paths: []\n", encoding="utf-8")
    src = proj / "src"
    src.mkdir()
    (src / "bad.py").write_text("import openai\n", encoding="utf-8")

    result = _run_cli(str(proj))
    assert result.returncode == 1
    assert "bad.py:1:openai" in result.stdout


def test_cli_exit_2_on_config_error(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = _run_cli(
        str(empty),
        "--blocklist",
        str(empty / "missing-blocklist.yaml"),
    )
    assert result.returncode == 2
    assert "blocklist not found" in result.stderr
