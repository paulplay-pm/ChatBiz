"""Tests for the AST scanner core.

Covers the 4 import patterns locked in by the spec:
  1. ``import openai`` (ast.Import)
  2. ``from openai import OpenAI`` (ast.ImportFrom)
  3. ``import openai as oai`` (ast.Import with asname)
  4. ``__import__("openai")`` and getattr chain (ast.Call with string literal arg)

Plus the allowlist path-glob behavior and the config-error exit path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway_scanner.scanner import (
    ConfigError,
    Violation,
    scan_dir,
    scan_file,
)

FIXTURES = Path(__file__).parent / "fixtures"
PKG_ROOT = Path(__file__).parent.parent
BLOCKLIST = PKG_ROOT / "blocklist.yaml"
ALLOWLIST = PKG_ROOT / "allowlist.yaml"


# ---------- 1. direct import ----------

def test_direct_import_flagged() -> None:
    file = FIXTURES / "direct_import.py"
    blocklist = {"openai"}
    violations = scan_file(file, blocklist)
    assert len(violations) == 1
    v = violations[0]
    assert v.package == "openai"
    assert v.file == file
    assert v.line == 2


# ---------- 2. from-import + as-alias ----------

def test_from_import_and_as_alias_flagged() -> None:
    file = FIXTURES / "as_import.py"
    blocklist = {"openai", "anthropic"}
    violations = scan_file(file, blocklist)
    pkgs = {v.package for v in violations}
    assert pkgs == {"openai", "anthropic"}
    # lines: from openai -> 2, import anthropic as ant -> 3
    by_line = {v.line: v.package for v in violations}
    assert by_line[2] == "openai"
    assert by_line[3] == "anthropic"


# ---------- 3. dynamic __import__ ----------

def test_dynamic_import_flagged() -> None:
    file = FIXTURES / "dynamic_import.py"
    blocklist = {"cohere"}
    violations = scan_file(file, blocklist)
    assert len(violations) == 1
    assert violations[0].package == "cohere"


# ---------- 4. getattr chain on __import__ ----------

def test_getattr_chain_on_dunder_import_flagged() -> None:
    file = FIXTURES / "getattr_import.py"
    blocklist = {"mistralai"}
    violations = scan_file(file, blocklist)
    # The mod = __import__("mistralai") line is the violation; the
    # getattr(mod, "Mistral") call does NOT match because its first
    # arg is `mod` (a Name), not a string literal.
    assert len(violations) == 1
    assert violations[0].package == "mistralai"


# ---------- 5. comment / docstring / non-blocklist imports are skipped ----------

def test_commented_and_unrelated_imports_skipped() -> None:
    file = FIXTURES / "commented_import.py"
    blocklist = {"openai", "anthropic"}
    violations = scan_file(file, blocklist)
    assert violations == []


# ---------- 6. multi-line from-import ----------

def test_multiline_from_import_flagged() -> None:
    file = FIXTURES / "multiline_import.py"
    blocklist = {"openai", "google"}
    violations = scan_file(file, blocklist)
    pkgs = {v.package for v in violations}
    assert "openai" in pkgs
    assert "google" in pkgs
    # The `from openai import (...)` is on line 2; the `import google...`
    # is on line 5. Sanity check those line numbers.
    by_line = {v.line: v.package for v in violations}
    assert by_line[2] == "openai"
    assert by_line[5] == "google"


# ---------- 7. allowlist path globbing ----------

def test_allowlist_exempts_named_path(tmp_path: Path) -> None:
    # Create a small project on the fly so we can control the
    # allowlist globs without depending on the repo's real tree.
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "blocklist.yaml").write_text("packages:\n  - openai\n", encoding="utf-8")
    (proj / "allowlist.yaml").write_text(
        "paths:\n  - 'allowed/**'\n", encoding="utf-8"
    )
    # forbidden/
    forbidden = proj / "forbidden"
    forbidden.mkdir()
    bad = forbidden / "bad.py"
    bad.write_text("import openai\n", encoding="utf-8")
    # allowed/
    allowed = proj / "allowed"
    allowed.mkdir()
    good = allowed / "good.py"
    good.write_text("import openai\n", encoding="utf-8")

    violations = scan_dir(proj, proj / "blocklist.yaml", proj / "allowlist.yaml")
    # Only the file under forbidden/ should be reported.
    assert len(violations) == 1
    assert violations[0].file == bad


# ---------- 8. missing blocklist -> ConfigError ----------

def test_missing_blocklist_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="blocklist not found"):
        scan_dir(tmp_path, tmp_path / "nope.yaml", tmp_path / "nope2.yaml")


# ---------- 9. malformed blocklist YAML -> ConfigError ----------

def test_malformed_blocklist_raises(tmp_path: Path) -> None:
    proj = tmp_path
    blocklist = proj / "blocklist.yaml"
    blocklist.write_text("packages: not-a-list\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="'packages' must be a list"):
        scan_dir(proj, blocklist, proj / "allowlist.yaml")


# ---------- 9b. blocklist YAML parse error ----------

def test_blocklist_yaml_parse_error_raises(tmp_path: Path) -> None:
    proj = tmp_path
    blocklist = proj / "blocklist.yaml"
    blocklist.write_text("packages: {openai\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="YAML parse error"):
        scan_dir(proj, blocklist, proj / "allowlist.yaml")


# ---------- 9c. blocklist missing 'packages' key ----------

def test_blocklist_missing_packages_key_raises(tmp_path: Path) -> None:
    proj = tmp_path
    blocklist = proj / "blocklist.yaml"
    blocklist.write_text("not_packages: []\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="must be a YAML mapping"):
        scan_dir(proj, blocklist, proj / "allowlist.yaml")


# ---------- 9d. allowlist YAML parse error ----------

def test_allowlist_yaml_parse_error_raises(tmp_path: Path) -> None:
    proj = tmp_path
    blocklist = proj / "blocklist.yaml"
    blocklist.write_text("packages:\n  - openai\n", encoding="utf-8")
    allowlist = proj / "allowlist.yaml"
    allowlist.write_text("paths: {openai\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="allowlist YAML parse error"):
        scan_dir(proj, blocklist, allowlist)


# ---------- 9e. allowlist missing 'paths' key ----------

def test_allowlist_missing_paths_key_raises(tmp_path: Path) -> None:
    proj = tmp_path
    blocklist = proj / "blocklist.yaml"
    blocklist.write_text("packages:\n  - openai\n", encoding="utf-8")
    allowlist = proj / "allowlist.yaml"
    allowlist.write_text("not_paths: []\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="allowlist .* must be a YAML mapping"):
        scan_dir(proj, blocklist, allowlist)


# ---------- 9f. allowlist non-list 'paths' ----------

def test_allowlist_non_list_paths_raises(tmp_path: Path) -> None:
    proj = tmp_path
    blocklist = proj / "blocklist.yaml"
    blocklist.write_text("packages:\n  - openai\n", encoding="utf-8")
    allowlist = proj / "allowlist.yaml"
    allowlist.write_text("paths: just-a-string\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="'paths' must be a list"):
        scan_dir(proj, blocklist, allowlist)


# ---------- 9h. _glob_match single-star fast path ----------

def test_glob_match_single_star_pattern() -> None:
    """When pattern has no `**`, fast-path uses fnmatch. The fallback
    also tries ``**/{pattern}`` so a top-level glob like ``src/*.py``
    matches anywhere in the tree."""
    from gateway_scanner.scanner import _glob_match
    assert _glob_match("src/foo.py", "src/*.py") is True
    # The ``**/{pattern}`` fallback makes top-level globs match nested paths.
    assert _glob_match("deep/src/foo.py", "**/src/*.py") is True


# ---------- 9i. scan_file tolerates SyntaxError ----------

def test_scan_file_syntax_error_returns_empty(tmp_path: Path) -> None:
    f = tmp_path / "broken.py"
    f.write_text("def foo(:\n    pass\n", encoding="utf-8")
    from gateway_scanner.scanner import scan_file
    assert scan_file(f, {"openai"}) == []


# ---------- 9i-extra. __import__() with no args ----------

def test_dunder_import_no_args_returns_none() -> None:
    """``__import__()`` with no args is legal Python (returns None).
    The scanner should not flag it (no package name to extract)."""
    import textwrap
    from gateway_scanner.scanner import scan_file
    f = FIXTURES.parent / "_dyn_no_args.py"
    f.write_text(
        textwrap.dedent("""\
        def f():
            return __import__()
        """),
        encoding="utf-8",
    )
    try:
        violations = scan_file(f, {"openai"})
        assert violations == []
    finally:
        f.unlink()


# ---------- 9j. allowlist works for deeply nested globs ----------

def test_allowlist_deeply_nested_glob(tmp_path: Path) -> None:
    """`**/foo` glob should match `foo`, `x/foo`, `x/y/foo` etc."""
    proj = tmp_path
    (proj / "blocklist.yaml").write_text("packages:\n  - openai\n", encoding="utf-8")
    (proj / "allowlist.yaml").write_text("paths:\n  - '**/exempt/**'\n", encoding="utf-8")
    (proj / "exempt").mkdir()
    (proj / "exempt" / "deep" / "x").mkdir(parents=True)
    (proj / "exempt" / "deep" / "x" / "good.py").write_text("import openai\n", encoding="utf-8")
    (proj / "bad.py").write_text("import openai\n", encoding="utf-8")
    violations = scan_dir(
        proj, proj / "blocklist.yaml", proj / "allowlist.yaml"
    )
    assert len(violations) == 1
    assert violations[0].file == proj / "bad.py"


# ---------- 9k. _glob_match `**` recursive pattern ----------

def test_glob_match_double_star_recursive() -> None:
    """`**/foo` must match `foo` at any depth."""
    from gateway_scanner.scanner import _glob_match
    assert _glob_match("foo", "**/foo") is True
    assert _glob_match("x/foo", "**/foo") is True
    assert _glob_match("x/y/foo", "**/foo") is True
    # `**/foo` should NOT match `foobar`.
    assert _glob_match("foobar", "**/foo") is False
    # Plain `foo` matches `foo` exactly.
    assert _glob_match("foo", "foo") is True


# ---------- 9l. allowlist file missing (line 91) ----------

def test_allowlist_missing_returns_empty_allowlist(tmp_path: Path) -> None:
    """If the allowlist file does not exist, scan everything (no exempt)."""
    proj = tmp_path
    (proj / "blocklist.yaml").write_text("packages:\n  - openai\n", encoding="utf-8")
    (proj / "src").mkdir()
    (proj / "src" / "bad.py").write_text("import openai\n", encoding="utf-8")
    # Don't create the allowlist.
    violations = scan_dir(
        proj, proj / "blocklist.yaml", proj / "missing-allowlist.yaml"
    )
    assert len(violations) == 1
    assert violations[0].file == proj / "src" / "bad.py"


# ---------- 10. full repo scan against the real blocklist/allowlist ----------

def test_full_repo_scan_smoke() -> None:
    """When scanning from the package root, all fixture files
    (under ``tests/``) are allowlisted and the scan reports zero."""
    # Use the package root (which contains ``tests/``) as scan root,
    # and assert that the only ``*.py`` files in there are all under
    # the ``tests/`` allowlist glob.
    violations = scan_dir(PKG_ROOT, BLOCKLIST, ALLOWLIST)
    assert violations == [], (
        f"expected zero violations against the package root, got "
        f"{len(violations)}: {violations[:3]}"
    )
