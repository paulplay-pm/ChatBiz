"""PII detector — scan text, return ordered, non-overlapping matches.

The detector is a *pure* function (``text -> [PIIMatch]``); it
does not touch Redis or the PII map. The redactor (Phase 4 task
5.3) wraps this with the placeholder-construction and persistence
logic. Keeping the detector pure lets us unit-test every rule in
isolation without fakeredis, and lets the redactor add the
trace-keyed map as a separate concern.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.pii.rules import RULES, validate_rule


@dataclass(frozen=True)
class PIIMatch:
    """A single PII hit, with byte offsets into the source text.

    The offsets are Python ``str`` indices, which for ASCII matches
    are also byte offsets; for multibyte content (e.g. a Chinese
    营收 amount followed by a Latin card number) the offsets are
    Unicode code-point indices — that is fine because the redactor
    substitutes on the Python ``str`` itself rather than the byte
    buffer.
    """

    type: str
    start: int
    end: int
    value: str


def detect(text: str) -> list[PIIMatch]:
    """Return all PII hits in ``text``, deduped + non-overlapping.

    The dedup rule is **longest-first** within a tied start position:
    if the email regex and a numeric regex both fire at the same
    offset (e.g. ``1234567890123456@example.com``), the longer match
    wins. Across disjoint spans, the *leftmost* match wins.

    Algorithm:

    1. Run every rule's regex, keep only matches that pass
       :func:`validate_rule` (this is where Luhn / 身份证 / USCC
       pruning happens).
    2. Sort by ``(start, -length)`` so longer matches are tried first
       at any given start offset.
    3. Greedy sweep: keep a match only if its start is ``>=`` the
       last kept end. The negative-length sort key guarantees that
       at a colliding start position, the longer match is processed
       first and the shorter one is dropped.
    """
    matches: list[PIIMatch] = []
    for rule in RULES:
        for m in rule.pattern.finditer(text):
            value = m.group(0)
            if not validate_rule(rule.name, value):
                continue
            matches.append(PIIMatch(rule.name, m.start(), m.end(), value))
    # 按 start 排序,重叠区间取最长
    matches.sort(key=lambda x: (x.start, -(x.end - x.start)))
    deduped: list[PIIMatch] = []
    last_end = -1
    for m in matches:
        if m.start >= last_end:
            deduped.append(m)
            last_end = m.end
    return deduped


__all__ = ["PIIMatch", "detect"]
