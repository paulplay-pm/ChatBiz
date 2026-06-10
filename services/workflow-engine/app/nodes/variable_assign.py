"""Variable assignment node — bind Jinja2-rendered values into the workflow state.

Each entry in ``vars`` maps an output key to either:
  * a string containing ``{{...}}`` or ``{%...%}`` (rendered as Jinja2 against inputs)
  * anything else (used as a literal)

This is the most common node in a workflow — it threads intermediate values
into later nodes' input mappings. We deliberately keep it simple: no list
construction, no nested objects, no arithmetic. Those go through the LLM or
Code nodes.
"""
from __future__ import annotations

from typing import Any

from pydantic import Field

from app.graph.jinja import render_jinja
from app.nodes.contracts.base import BaseConfig, BaseNode
from app.nodes.registry import register


class VariableAssignConfig(BaseConfig):
    """Configuration for the variable-assignment node."""

    vars: dict[str, Any] = Field(
        default_factory=dict,
        description="Variable name → Jinja2 表达式 or literal value (strings with {{ }} are rendered)",
    )


@register("variable_assign", version="1.0.0")
class VariableAssignNode(BaseNode):
    """Node contract for variable assignment."""

    config: VariableAssignConfig


async def variable_assign_execute(config: VariableAssignConfig, inputs: dict) -> dict:
    """Render each variable — Jinja2 template if string-with-marker, literal otherwise.

    The output dict has one key per entry in ``config.vars``. Keys with ``None``
    template strings (e.g. ``{"k": None}``) are rendered as ``None``.
    """
    out: dict[str, Any] = {}
    for k, v in config.vars.items():
        if isinstance(v, str) and ("{{" in v or "{%" in v):
            out[k] = render_jinja(v, inputs)
        else:
            out[k] = v
    return out


__all__ = ["VariableAssignConfig", "VariableAssignNode", "variable_assign_execute"]
