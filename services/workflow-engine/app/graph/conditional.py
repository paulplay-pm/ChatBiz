"""Conditional edge router helpers.

A workflow's canvas JSON encodes conditional edges as
``{"from": "n1", "to": "n2", "condition": "{{ score > 80 }}", "default": "n3"}``.
The compiler (``app/graph/compiler.py``) wires these into LangGraph
``add_conditional_edges`` by wrapping a router function that calls
``evaluate_condition(expression, state)``.

Truthy / falsy semantics match the spec: ``"true" / "True" / "1" / "yes"``
are truthy; ``"false" / "False" / "0" / "no" / ""`` are falsy; integers
parse via ``int(...)``; everything else falls through to Python's
``bool()`` with a lowercase guard against the literal string ``"false"``
(a common gotcha: a non-empty string is truthy in Python, but ``"false"``
should clearly be falsy for boolean expressions).
"""
from __future__ import annotations

from typing import Any

_TRUTHY = {"true", "True", "1", "yes"}
_FALSY = {"false", "False", "0", "no", ""}


def evaluate_condition(expression: str, state: dict) -> bool:
    """Evaluate a Jinja2 boolean expression in the context of ``state``.

    Args:
        expression: Jinja2 template string. Typically a comparison
            (``{{ score > 80 }}``) or a variable reference
            (``{{ is_approved }}``). The rendered value is interpreted
            using the truthy / falsy rules above.
        state: The LangGraph state dict. All keys are available as
            template variables.

    Returns:
        ``True`` if the rendered expression is truthy, ``False`` otherwise.

    Raises:
        UserError: propagated from ``render_jinja`` when the template
            references a missing variable. Boundary #3 — the workflow
            definition is malformed.
    """
    from app.graph.jinja import render_jinja

    rendered = render_jinja(expression, state)
    if rendered in _TRUTHY:
        return True
    if rendered in _FALSY:
        return False
    try:
        return bool(int(rendered))
    except (ValueError, TypeError):
        # Fallback: Python's bool(), with a guard against the literal
        # string "false" (which is truthy as a non-empty string).
        return bool(rendered) and str(rendered).lower() != "false"


__all__ = ["evaluate_condition"]
