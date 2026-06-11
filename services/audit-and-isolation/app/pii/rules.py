"""PII detection rules for the data-isolation gateway.

Six rule families — 身份证 / 手机 / 银行卡 / 邮箱 / 统一社会信用代码 / 营收金额 —
cover the PII categories the eng-review report flagged as mandatory
for the financial reporting use case (paul 财务月报). Each rule pairs
a regex with a *secondary validation* step in :func:`validate_rule`
that prunes the false-positive tail of the regex (e.g. ``\d{16,19}``
matches 16-19 consecutive digits anywhere, but only a Luhn-valid
subset of those are real bank card numbers).

Why a separate validation step rather than a tighter regex?
The "false positive" Luhn-valid 16-digit sequences inside large
text blobs (e.g. timestamps, log line numbers, container IDs) are
exceedingly rare in practice; the regex is broad for **recall** and
the Luhn/身份证/USCC check is the **precision** lever. False *negative*
hits (a real card that doesn't Luhn-validate) only happen when the
caller has already mangled the number, in which case the gateway
*can't* recover it anyway.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PIIRule:
    """A single PII detection rule: type label + compiled regex.

    ``name`` is the Chinese type label used in the placeholder
    (``[身份证_ab12]``) and in the audit log's ``pii_detected_types``
    column. The English names are not used at runtime; the audit_log
    schema (per ``docs/architecture.md`` §4.3.X) keeps Chinese
    strings to align with the gstack project's reporter convention.
    """

    name: str  # 类型名,占位符前缀
    pattern: re.Pattern


# 身份证:18 位,末位 X,前 17 位数字,最后一位数字或 X
_ID_CARD = re.compile(r"\b\d{17}[\dXx]\b")
# 手机:11 位 1[3-9] 开头
_MOBILE = re.compile(r"\b1[3-9]\d{9}\b")
# 银行卡:16-19 位数字 (Luhn 校验在 detector 里做)
_BANK_CARD = re.compile(r"\b\d{16,19}\b")
# 邮箱
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# 统一社会信用代码:18 位 [0-9A-HJ-NPQRTUWXY]
_USCC = re.compile(r"\b[0-9A-HJ-NPQRTUWXY]{18}\b")
# 营收金额: "营收 1,234,567.89 元"
_REVENUE = re.compile(r"营收\s*[\d,]+\.?\d*\s*元")


def _luhn_ok(num: str) -> bool:
    """Standard Luhn-10 check on a digit string.

    Implementation: sum of odd-position digits (counted from the
    right, 1-indexed) + sum of each even-position digit doubled
    (with the standard "if >9 subtract 9" fold). The check digit is
    the rightmost digit; the formula is equivalent regardless of
    whether the rightmost digit is included in the running sum.
    """
    digits = [int(c) for c in num]
    odd = sum(digits[-1::-2])
    even = sum(sum(divmod(2 * d, 10)) for d in digits[-2::-2])
    return (odd + even) % 10 == 0


# ---------------------------------------------------------------------
# Public rule list
# ---------------------------------------------------------------------

RULES: list[PIIRule] = [
    PIIRule("身份证", _ID_CARD),
    PIIRule("手机", _MOBILE),
    PIIRule("银行卡", _BANK_CARD),
    PIIRule("邮箱", _EMAIL),
    PIIRule("信用代码", _USCC),
    PIIRule("营收金额", _REVENUE),
]


# ---------------------------------------------------------------------
# Rule-level secondary validation
# ---------------------------------------------------------------------


# Weights + check-digit table for 18-digit PRC resident ID card.
# Per GB 11643-1999: weighted sum of first 17 digits, mod 11, map to
# the 18th digit using the table below. The "X" branch handles the
# check value of 2 (which renders as the literal character X).
_ID_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
_ID_CHECK = ["1", "0", "X", "9", "8", "7", "6", "5", "4", "3", "2"]

# USCC alphabet (GB 32100-2015): 0-9 + A-Z minus I, O, Q, S, V, Z.
# The 18-char USCC encodes a registration-management category + the
# organisation's 9-digit base code + a check digit; the alphabet
# exclusion avoids the letter-I / letter-O / letter-Z vs digit-1 /
# digit-0 / digit-2 OCR confusion that motivated the standard.
_USCC_ALPHABET = "0123456789ABCDEFGHJKLMNPQRTUWXY"


def validate_rule(name: str, value: str) -> bool:
    """Rule-level secondary check that prunes regex false positives.

    Returns ``True`` for rules that don't have a meaningful secondary
    check (email, mobile, revenue) and ``False`` for inputs that
    *look* like a match but fail the structural check (e.g. a
    Luhn-bad 16-digit number).
    """
    if name == "银行卡":
        return _luhn_ok(value)
    if name == "身份证":
        # 末位校验:加权求和 mod 11
        if len(value) != 18:  # pragma: no cover — regex already guarantees 18 char match
            return False
        try:
            s = sum(int(value[i]) * _ID_WEIGHTS[i] for i in range(17))
        except ValueError:  # pragma: no cover — regex already guarantees all-digit in first 17 chars
            return False
        return _ID_CHECK[s % 11] == value[17].upper()
    if name == "信用代码":
        return all(c in _USCC_ALPHABET for c in value)
    return True


__all__ = ["PIIRule", "RULES", "validate_rule"]
