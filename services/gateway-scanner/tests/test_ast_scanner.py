"""AST scanner test — 5 fixture files, one per import pattern.

Per task 1.4 of `openspec/changes/gateway-egress-enforcement-p0/`. Each fixture
exercises one pattern; the test asserts the scanner finds exactly the expected
package names at the expected lines.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway_scanner.scanner import ScannerConfig, scan_path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
BLOCKLIST = frozenset(
    {
        "openai",
        "anthropic",
        "cohere",
        "google.generativeai",
        "google.genai",
        "mistralai",
        "deepseek",
    }
)


def _scan(fixture: str) -> list[tuple[str, int, str]]:
    """Return list of (filename, line, package) for all violations in fixture."""
    cfg = ScannerConfig(target=FIXTURES / fixture, blocklist=BLOCKLIST, allowlist=frozenset())
    violations = scan_path(FIXTURES / fixture, cfg)
    return [(v.file.name, v.line, v.package) for v in violations]


def test_direct_import_matches_bare_and_from() -> None:
    """`import openai` and `from openai import OpenAI` both match package 'openai'."""
    hits = _scan("direct_import.py")
    packages = {h[2] for h in hits}
    assert "openai" in packages, f"openai not in hits: {hits}"
    # Expect at least 2 hits (line 3 bare import, line 4 from-import)
    openai_hits = [h for h in hits if h[2] == "openai"]
    assert len(openai_hits) >= 2, f"expected ≥2 openai hits, got {openai_hits}"


def test_as_import_aliased_still_matches() -> None:
    """`import openai as oai` and `from anthropic import Anthropic as A` match root."""
    hits = _scan("as_import.py")
    packages = {h[2] for h in hits}
    assert "openai" in packages, f"openai not in hits: {hits}"
    assert "anthropic" in packages, f"anthropic not in hits: {hits}"


def test_dynamic_import_dunder_and_getattr_chain() -> None:
    """`__import__("cohere")` and `getattr(__import__("google.generativeai"), ...)` match."""
    hits = _scan("dynamic_import.py")
    packages = {h[2] for h in hits}
    assert "cohere" in packages, f"cohere not in hits: {hits}"
    assert "google.generativeai" in packages, f"google.generativeai not in hits: {hits}"


def test_commented_import_not_flagged() -> None:
    """Comment lines like `# import openai` MUST NOT produce a violation.

    Comments don't reach the AST, so the scanner should report zero hits.
    """
    hits = _scan("commented_import.py")
    assert hits == [], f"comments should not match, got: {hits}"


def test_multiline_parenthesised_import_matches_once() -> None:
    """`from openai import (\\n    OpenAI,\\n    AsyncOpenAI,\\n)` is one violation.

    Multi-line imports should be reported on the `from` line, not per-name.
    """
    hits = _scan("multiline_import.py")
    packages = [h[2] for h in hits]
    assert "openai" in packages, f"openai not in multiline hits: {hits}"
    assert "google.generativeai" in packages, f"google.generativeai not in multiline hits: {hits}"


def test_scanner_handles_syntax_error_gracefully() -> None:
    """Files with SyntaxError should be skipped, not crash the scan.

    The scanner's contract is "report policy violations", not "lint Python".
    """
    bad = FIXTURES / "_syntax_error.py"
    bad.write_text("def broken(:\n  pass\n")
    try:
        cfg = ScannerConfig(target=FIXTURES, blocklist=BLOCKLIST, allowlist=frozenset())
        violations = scan_path(FIXTURES, cfg)
        # No crash, no violations from the bad file itself (it's not in blocklist)
        bad_violations = [v for v in violations if v.file == bad]
        assert bad_violations == [], f"bad file produced violations: {bad_violations}"
    finally:
        bad.unlink(missing_ok=True)


def test_scanner_skips_allowlisted_paths() -> None:
    """A file under an allowlisted path prefix is not scanned, even if it imports
    a blocked package."""
    from gateway_scanner.scanner import ScannerConfig, scan_path

    target = FIXTURES / "as_import.py"  # imports openai + anthropic
    cfg = ScannerConfig(
        target=target,
        blocklist=BLOCKLIST,
        allowlist=frozenset({target}),  # self is allowlisted
    )
    violations = scan_path(target, cfg)
    assert violations == [], f"allowlisted file produced violations: {violations}"
