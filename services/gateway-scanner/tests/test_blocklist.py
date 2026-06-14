"""Blocklist test — verifies blocklist.yaml exists, parses, and every entry is a valid identifier.

Per task 1.2 of `openspec/changes/gateway-egress-enforcement-p0/`. Failure of any
assertion here means the scanner can't load its blocklist (silent policy
bypass risk).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
BLOCKLIST = ROOT / "blocklist.yaml"

# Valid Python package names: lowercase letter/digit/underscore, separated by
# dots. Dotted names like `google.generativeai` are real sub-packages.
_PKG_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")


def test_blocklist_file_exists() -> None:
    assert BLOCKLIST.is_file(), f"missing {BLOCKLIST}"


def test_blocklist_parses_as_yaml_list() -> None:
    data = yaml.safe_load(BLOCKLIST.read_text())
    assert isinstance(data, list), f"blocklist must be a YAML list, got {type(data)}"
    assert len(data) > 0, "blocklist is empty — would silently pass every scan"


def test_blocklist_entries_are_strings() -> None:
    data = yaml.safe_load(BLOCKLIST.read_text())
    for i, entry in enumerate(data):
        assert isinstance(entry, str), f"entry {i} is not a string: {entry!r}"


def test_blocklist_entries_match_python_identifier_shape() -> None:
    data = yaml.safe_load(BLOCKLIST.read_text())
    for entry in data:
        assert _PKG_NAME_RE.match(entry), (
            f"entry {entry!r} doesn't look like a Python package name "
            f"(lowercase letters/digits/underscore, optional dot)"
        )


def test_blocklist_compiles_via_tokenize() -> None:
    """Every blocklist entry should be a valid Python `import X` target.

    Sanity check: if `import <entry>` would be a SyntaxError or NameError at
    the source level, the scanner can't meaningfully flag it. We use compile
    (not exec) to verify syntactic well-formedness of each entry as a name.
    """
    import ast
    data = yaml.safe_load(BLOCKLIST.read_text())
    for entry in data:
        # Build `import <entry>` and parse; the parser only checks syntax.
        # We don't execute.
        tree = ast.parse(f"import {entry}")
        # Should produce exactly one ast.Import node with names[0].name == entry
        assert isinstance(tree, ast.Module)
        assert len(tree.body) == 1 and isinstance(tree.body[0], ast.Import)
        assert tree.body[0].names[0].name == entry


def test_blocklist_includes_required_providers() -> None:
    """The 6 provider names called out in the task spec must be present."""
    data = yaml.safe_load(BLOCKLIST.read_text())
    required = {"openai", "anthropic", "cohere", "google.generativeai", "mistralai", "deepseek"}
    missing = required - set(data)
    assert not missing, f"blocklist missing required providers: {missing}"


def test_blocklist_has_no_duplicates() -> None:
    data = yaml.safe_load(BLOCKLIST.read_text())
    assert len(data) == len(set(data)), f"blocklist has duplicates: {data}"


def test_blocklist_documented_at_top() -> None:
    """The file's first line should be a YAML comment explaining its purpose."""
    first = BLOCKLIST.read_text().splitlines()[0]
    assert first.startswith("#"), f"first line should be a comment, got: {first!r}"
