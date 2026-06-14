"""Allowlist test — verifies allowlist.yaml exists, parses, and every path exists in the repo.

Per task 1.3 of `openspec/changes/gateway-egress-enforcement-p0/`. The
allowlist is the only way to whitelist a real LLM SDK import (rare, e.g.
test fixtures that monkeypatch the SDK). Every entry MUST resolve to a real
path, otherwise the scanner silently allows nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
# Allowlist paths are relative to the main repo root (the scanner walks
# arbitrary user-provided paths, but the allowlist itself lives in the
# gateway-scanner package and references repo-relative paths).
REPO_ROOT = ROOT.parent.parent
ALLOWLIST = ROOT / "allowlist.yaml"


def test_allowlist_file_exists() -> None:
    assert ALLOWLIST.is_file(), f"missing {ALLOWLIST}"


def test_allowlist_parses_as_yaml_list() -> None:
    data = yaml.safe_load(ALLOWLIST.read_text())
    assert isinstance(data, list), f"allowlist must be a YAML list, got {type(data)}"
    assert len(data) > 0, "allowlist is empty"


def test_allowlist_entries_are_strings() -> None:
    data = yaml.safe_load(ALLOWLIST.read_text())
    for i, entry in enumerate(data):
        assert isinstance(entry, str), f"entry {i} is not a string: {entry!r}"


def test_allowlist_paths_exist() -> None:
    """Each entry must resolve to a real path under the repo root.

    Directories and files are both allowed. Symlinks are resolved before
    comparison.
    """
    data = yaml.safe_load(ALLOWLIST.read_text())
    for entry in data:
        candidate = (REPO_ROOT / entry).resolve()
        assert candidate.exists(), (
            f"allowlist entry {entry!r} does not exist at {candidate}. "
            f"Either create the path or remove the entry."
        )


def test_allowlist_documented_at_top() -> None:
    first = ALLOWLIST.read_text().splitlines()[0]
    assert first.startswith("#"), f"first line should be a comment, got: {first!r}"


def test_allowlist_no_self_reference_to_active_scanner_code() -> None:
    """Safety: the scanner's own `scanner.py` / `__main__.py` MUST NOT be
    in the allowlist (they're policy enforcers, not policy violators).

    The `services/gateway-scanner/` prefix in the allowlist is fine because
    the *test* directory there is what needs the exemption. But listing
    individual scanner source files would defeat the purpose.
    """
    data = yaml.safe_load(ALLOWLIST.read_text())
    forbidden = {
        "services/gateway-scanner/gateway_scanner/scanner.py",
        "services/gateway-scanner/gateway_scanner/__main__.py",
    }
    bad = forbidden & set(data)
    assert not bad, f"scanner source files appear in allowlist: {bad}"


def test_allowlist_gitignored_paths_warn() -> None:
    """.venv / __pycache__ / node_modules are never legitimate targets; if
    they appear in the allowlist, the entry is likely wrong."""
    data = yaml.safe_load(ALLOWLIST.read_text())
    for entry in data:
        assert ".venv" not in entry, f"allowlist entry contains .venv: {entry!r}"
        assert "__pycache__" not in entry, f"allowlist entry contains __pycache__: {entry!r}"
        assert "node_modules" not in entry, f"allowlist entry contains node_modules: {entry!r}"
