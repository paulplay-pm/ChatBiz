"""Unit tests for app/graph/conditional.py — evaluate_condition."""
from app.graph.conditional import evaluate_condition


def test_true_string_variants():
    for v in ("true", "True", "TRUE", "1", "yes", "y"):
        assert evaluate_condition(v, {}) is True, f"expected True for {v!r}"


def test_false_string_variants():
    for v in ("false", "False", "FALSE", "0", "no", ""):
        assert evaluate_condition(v, {}) is False, f"expected False for {v!r}"


def test_int_zero_is_false():
    assert evaluate_condition("0", {}) is False
    assert evaluate_condition("0", {}) is False


def test_int_positive_is_true():
    assert evaluate_condition("1", {}) is True
    assert evaluate_condition("42", {}) is True
    assert evaluate_condition("100", {}) is True


def test_nonempty_string_is_true():
    assert evaluate_condition("hello", {}) is True


def test_explicit_false_string_is_false():
    """'false' is False, but 'falseish' is True (truthy non-empty string)."""
    assert evaluate_condition("false", {}) is False
    assert evaluate_condition("hello", {}) is True
    assert evaluate_condition("falseish", {}) is True  # 'false' substring doesn't override
