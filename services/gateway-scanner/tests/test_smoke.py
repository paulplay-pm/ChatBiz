"""Smoke test for gateway-scanner CLI — verifies 3-tier exit code contract.

Per task 1.1 step 1.1.7: scan a clean dir → exit 0, scan a dir with violation
→ exit 1, scan a non-existent path → exit 2. This is the only test in task
1.1; full AST pattern coverage (4 patterns) lives in tests/test_ast_scanner.py
(task 1.4) and blocklist/allowlist tests in tests/test_blocklist.py +
tests/test_allowlist.py (tasks 1.2 / 1.3).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"


def _run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke `python -m gateway_scanner` with given args.

    Uses `sys.executable` so the test environment matches the installed
    interpreter (works in both `pip install -e .` and `uv` workflows).
    """
    return subprocess.run(
        [sys.executable, "-m", "gateway_scanner", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_exit_0_clean_dir(tmp_path: Path) -> None:
    """Scan an empty directory with no rules → exit 0 (clean)."""
    result = _run_cli(str(tmp_path), cwd=ROOT)
    assert result.returncode == 0, f"expected 0, got {result.returncode}\nstderr: {result.stderr}"
    assert "clean" in result.stderr.lower()


def test_exit_1_violation_found(tmp_path: Path) -> None:
    """Scan a directory containing a banned import → exit 1 (violations)."""
    (tmp_path / "violator.py").write_text("import openai\n")
    blocklist = tmp_path / "blocklist.yaml"
    blocklist.write_text("- openai\n")
    result = _run_cli(str(tmp_path), "--blocklist", str(blocklist), cwd=ROOT)
    assert result.returncode == 1, f"expected 1, got {result.returncode}\nstderr: {result.stderr}"
    assert "violator.py" in result.stderr
    assert "openai" in result.stderr


def test_exit_2_path_not_found(tmp_path: Path) -> None:
    """Scan a non-existent path → exit 2 (setup error)."""
    missing = tmp_path / "does_not_exist_anywhere"
    result = _run_cli(str(missing), cwd=ROOT)
    assert result.returncode == 2, f"expected 2, got {result.returncode}\nstderr: {result.stderr}"
    assert "path not found" in result.stderr.lower() or "not found" in result.stderr.lower()


def test_exit_2_path_is_file(tmp_path: Path) -> None:
    """Scan a file (not a dir) → exit 2 (setup error)."""
    f = tmp_path / "a_file.py"
    f.write_text("x = 1\n")
    result = _run_cli(str(f), cwd=ROOT)
    assert result.returncode == 2, f"expected 2, got {result.returncode}\nstderr: {result.stderr}"
    assert "not a directory" in result.stderr.lower()


def test_default_path_is_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With no positional arg, scanner defaults to current directory."""
    # Create a clean subdir with no violations
    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "ok.py").write_text("import os\nimport sys\n")
    monkeypatch.chdir(clean)
    result = _run_cli(cwd=clean)  # no PATH arg → defaults to cwd
    assert result.returncode == 0, f"expected 0, got {result.returncode}\nstderr: {result.stderr}"


def test_violation_output_format(tmp_path: Path) -> None:
    """Violation lines must follow `file:line:package` format for CI parsers."""
    (tmp_path / "mod.py").write_text("import openai  # bypass attempt\n")
    blocklist = tmp_path / "blocklist.yaml"
    blocklist.write_text("- openai\n")
    result = _run_cli(str(tmp_path), "--blocklist", str(blocklist), cwd=ROOT)
    assert result.returncode == 1
    # Format check: <file>:<line>:<package> (rich may add a space after :)
    import re
    pat = re.compile(r"\S+\.py:\s*\d+:\s*openai")
    assert pat.search(result.stderr), f"no file:line:openai match in: {result.stderr}"


def test_pyproject_declares_only_three_runtime_deps() -> None:
    """Spec requirement: only pyyaml + click + rich (no FastAPI / DB)."""
    import tomllib

    with PYPROJECT.open("rb") as f:
        data = tomllib.load(f)
    deps = data["project"]["dependencies"]
    assert len(deps) == 3, f"expected 3 runtime deps, got {len(deps)}: {deps}"
    for d in deps:
        root = d.split(">")[0].split("=")[0].split("<")[0].split("~")[0].strip().lower()
        assert root in {"pyyaml", "click", "rich"}, f"unexpected dep: {d}"
