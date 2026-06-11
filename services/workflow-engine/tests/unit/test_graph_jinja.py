"""Unit tests for app/graph/jinja.py — render_jinja with StrictUndefined."""
import pytest
from app.graph.jinja import render_jinja


def test_plain_string_passthrough():
    assert render_jinja("hello world", {}) == "hello world"


def test_no_jinja_markers_passthrough():
    """If there are no Jinja markers, return input as-is (cheap path)."""
    assert render_jinja("plain text without markers", {}) == "plain text without markers"
    assert render_jinja("", {}) == ""


def test_non_string_passthrough():
    """Non-string inputs (dict/list/int) are returned unchanged — render_jinja is a string helper."""
    assert render_jinja({"key": "value"}, {}) == {"key": "value"}
    assert render_jinja(42, {}) == 42
    assert render_jinja([1, 2, 3], {}) == [1, 2, 3]
    assert render_jinja(None, {}) is None


def test_simple_jinja_variable():
    assert render_jinja("{{ name }}", {"name": "paul"}) == "paul"


def test_jinja_with_state_context():
    assert render_jinja("{{ n2.output.value }}", {"n2": {"output": {"value": "42"}}}) == "42"


def test_strict_undefined_raises_value_error():
    """StrictUndefined causes a ValueError when a variable is missing."""
    with pytest.raises(ValueError, match="Jinja2 渲染错误"):
        render_jinja("{{ undefined_var }}", {})


def test_jinja_if_construct():
    assert render_jinja("{% if x %}yes{% else %}no{% endif %}", {"x": True}) == "yes"
    assert render_jinja("{% if x %}yes{% else %}no{% endif %}", {"x": False}) == "no"
