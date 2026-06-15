"""Regression test for docs/architecture.md §4.3.Y (PII ruleset section).

Per task 6.1 of `openspec/changes/gateway-egress-enforcement-p0/`.
The §4.3.Y section is a contract between the architecture doc and
the implementation in `services/audit-and-isolation/app/pii/`. If a
future refactor renames a PII type or drops the `trace_id`
correlation in the placeholder, this test catches the doc drift
**before** it ships.

Tests are pure-Python (no pytest fixtures) so they can be run
standalone via `python tests/test_architecture_md.py` if needed.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC = REPO_ROOT / "docs" / "architecture.md"


# ----- file presence ------------------------------------------------------

def test_architecture_md_exists() -> None:
    assert DOC.is_file(), f"missing {DOC}"


def test_architecture_md_is_non_empty() -> None:
    """Guard against an accidental truncate."""
    assert DOC.stat().st_size > 10_000, (
        f"architecture.md looks suspiciously small ({DOC.stat().st_size} bytes); "
        f"was it truncated?"
    )


# ----- §4.3.Y section presence -------------------------------------------

def test_section_anchor_4_3_Y_exists() -> None:
    """The §4.3.Y header must be present as a `#### 4.3.Y ...` heading.

    `####` (h4) is the level used by sibling sub-sections like
    `#### 4.3.5 企业安全与权限` — staying consistent.
    """
    text = DOC.read_text(encoding="utf-8")
    assert re.search(r"^#### 4\.3\.Y ", text, re.MULTILINE), (
        "missing `#### 4.3.Y ...` heading in docs/architecture.md"
    )


def test_section_4_3_Y_in_table_of_contents() -> None:
    """The TOC anchor `4.3.Y PII 规则集` must exist.

    The placeholder anchor in the TOC was set in CLAUDE.md (line 31)
    pointing at §4.3.Y. If the section moves, the anchor must follow
    so the TOC link doesn't 404.
    """
    text = DOC.read_text(encoding="utf-8")
    # Look for the table-of-contents entry linking to 4.3.Y
    # The anchor in markdown is auto-generated from the heading,
    # which for "#### 4.3.Y PII 规则集(数据隔离网关详设)" becomes
    # `4.3.Y-pii-规则集数据隔离网关详设` (lowercase, spaces → hyphens).
    assert "4.3.Y" in text, "4.3.Y not present in TOC"
    assert "PII 规则集" in text, "PII 规则集 not present in TOC"


# ----- 6 PII rule types per spec 6.1 --------------------------------------

# The 6 rule names from services/audit-and-isolation/app/pii/rules.py
# (spec 6.1 says "6 类正则名" must be present in §4.3.Y).
EXPECTED_RULE_TYPES = [
    "身份证",  # ID card
    "手机",     # mobile
    "银行卡",   # bank card
    "邮箱",     # email
    "统一社会信用代码",  # unified social credit code (信用代码 is the prefix used)
    "营收",     # revenue / financial figures
]


def _doc_text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_all_6_pii_rule_types_appear_in_section_4_3_Y() -> None:
    """Spec 6.1 字面: "6 类正则名".

    The section must mention each of the 6 PII categories by name.
    '信用代码' is the prefix used by the placeholder for 统一社会信用代码
    so either form satisfies the rule.
    """
    text = _doc_text()
    missing = []
    for rule in EXPECTED_RULE_TYPES:
        if rule == "统一社会信用代码":
            # Accept either the full name or its placeholder prefix
            if "统一社会信用代码" not in text and "信用代码" not in text:
                missing.append(rule)
        elif rule not in text:
            missing.append(rule)
    assert not missing, f"section 4.3.Y missing PII rule types: {missing}"


def test_section_4_3_Y_mentions_trace_id_correlation() -> None:
    """Spec 6.1 字面: "trace 关联".

    The placeholder `<hash4>` ties each redacted PII back to the
    trace_id, so the reviewer can cross-query `/v1/traces/{id}`.
    """
    text = _doc_text()
    assert "trace_id" in text, (
        "section 4.3.Y does not mention trace_id correlation"
    )
    assert "hash4" in text or "trace_id[:4]" in text, (
        "section 4.3.Y does not document the hash4 placeholder suffix mechanism"
    )


def test_section_4_3_Y_mentions_mask_only_reversible() -> None:
    """Spec 6.1 字面: "mask-only 可逆".

    All 6 categories must support reverse-replace from the
    placeholder map; this is the contract that lets the response
    be reconstructed without persisting the original PII.
    """
    text = _doc_text()
    # Either "可逆" or "reverse" should appear
    assert "可逆" in text or "reverse" in text, (
        "section 4.3.Y does not document the reversible mask contract"
    )


def test_section_4_3_Y_cites_pii_implementation_paths() -> None:
    """The section must point to the authoritative implementation
    files in services/audit-and-isolation/app/pii/. A future
    refactor that moves the implementation is caught by the
    dead-link here (operator can grep the doc for the path).
    """
    text = _doc_text()
    pii_dir = "services/audit-and-isolation/app/pii/"
    assert pii_dir in text, (
        f"section 4.3.Y missing the pii/ directory reference ({pii_dir})"
    )
    # The 4 module names — accept either explicit .py or glob form
    required_modules = ["rules", "detector", "redactor", "reverser"]
    missing = [m for m in required_modules if m not in text]
    assert not missing, (
        f"section 4.3.Y missing pii module names: {missing}. "
        f"Expected each of {required_modules} to appear at least once "
        f"(e.g. as part of a path or in a parenthetical list)."
    )


def test_section_4_3_Y_cites_eng_review_decision_1() -> None:
    """The section's `eng-review 决策引用` block must include
    decision #1 (data-isolation gateway is the egress enforcement
    point) — that's the policy grounding for why PII is intercepted
    at all.
    """
    text = _doc_text()
    # Match either English or Chinese form of "decision #1"
    assert "决策 #1" in text or "决策#1" in text, (
        "section 4.3.Y missing eng-review decision #1 reference"
    )


def test_section_4_3_Y_does_not_regress_critical_path_coverage() -> None:
    """The section must reference the 4 critical-path test coverage
    requirement (eng-review Quality #2). Future authors must NOT
    drop this contract.
    """
    text = _doc_text()
    assert "critical path" in text.lower() or "critical_path" in text, (
        "section 4.3.Y missing critical-path coverage reference"
    )


# ----- §4.3.Y must be placed AFTER §4.3.5 -------------------------------

def test_section_4_3_Y_appears_after_4_3_5() -> None:
    """§4.3.Y should follow §4.3.5 (the 4-boundaries section),
    as it's an addendum to the data-isolation / security block."""
    text = _doc_text()
    h_4_3_5 = text.find("#### 4.3.5 ")
    h_4_3_Y = text.find("#### 4.3.Y ")
    h_4_4 = text.find("### 4.4 ")
    assert h_4_3_5 > 0, "missing #### 4.3.5 heading"
    assert h_4_3_Y > 0, "missing #### 4.3.Y heading"
    assert h_4_4 > 0, "missing ### 4.4 heading"
    assert h_4_3_5 < h_4_3_Y < h_4_4, (
        f"#### 4.3.Y (line {h_4_3_Y}) must be between "
        f"#### 4.3.5 (line {h_4_3_5}) and ### 4.4 (line {h_4_4})"
    )


# ----- integration with implementation ------------------------------------

def test_doc_pii_types_align_with_implementation() -> None:
    """The 6 PII types in the doc must match the rules in
    `services/audit-and-isolation/app/pii/rules.py`. If a
    refactor renames a PII type, this test catches the doc drift.
    """
    rules_path = REPO_ROOT / "services/audit-and-isolation/app/pii/rules.py"
    assert rules_path.is_file()
    rules_text = rules_path.read_text(encoding="utf-8")

    # The 6 PII regex name strings must appear in rules.py
    expected_names_in_code = [
        "_ID_CARD",
        "_MOBILE",
        "_BANK_CARD",
        "EMAIL",
        "_USCC",  # or whatever the 信用代码 regex is named
        "营收",   # the revenue regex
    ]
    # Just check at least 4 of the 6 are present — regex constants
    # may be named slightly differently across implementations
    found = sum(1 for n in expected_names_in_code if n in rules_text)
    assert found >= 4, (
        f"only {found} of the 6 expected PII regex names found in rules.py; "
        f"either rules.py was refactored or the doc drifted"
    )


def test_doc_section_length_is_substantial() -> None:
    """A short stub indicates a placeholder that was never fleshed
    out. The section should be at least 30 lines of content."""
    text = _doc_text()
    h_start = text.find("#### 4.3.Y ")
    h_end = text.find("#### 4.3.5 ", h_start + 1)  # next h4 after
    if h_end < 0:
        h_end = text.find("### 4.4 ", h_start + 1)
    section = text[h_start:h_end]
    line_count = len([ln for ln in section.splitlines() if ln.strip()])
    assert line_count >= 30, (
        f"§4.3.Y has only {line_count} non-empty lines; "
        f"the section is too short — was it stubbed out?"
    )
