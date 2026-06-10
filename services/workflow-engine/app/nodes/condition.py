"""Condition node — branch a workflow based on a Jinja2 boolean expression.

The ``expression`` is rendered as a Jinja2 template against the workflow
inputs; the rendered string is then coerced to a bool. The compiler reads
``outputs.branch`` to decide which outgoing edge to follow (true / false).

We coerce the rendered string because Jinja2 doesn't natively produce booleans
in a useful way for our graph semantics — users will write things like
``{{ count > 10 }}`` and we'll get back ``"True"`` or ``"False"``. The
truthy-coercion rules are spelled out in the execute function below.
"""
from __future__ import annotations

from pydantic import Field

from app.graph.jinja import render_jinja
from app.nodes.contracts.base import BaseConfig, BaseNode
from app.nodes.registry import register


class ConditionConfig(BaseConfig):
    """Configuration for the condition branch node."""

    expression: str = Field(
        ...,
        description="Jinja2 表达式,返回 truthy/falsy(字符串 'true'/'1'/'yes' → True,其余按 bool 强转)",
    )


@register("condition", version="1.0.0")
class ConditionNode(BaseNode):
    """Node contract for the condition branch node."""

    config: ConditionConfig


async def condition_execute(config: ConditionConfig, inputs: dict) -> dict:
    """Evaluate a Jinja2 expression. Returns ``{branch: bool, raw: str}``.

    The compiler wires ``branch`` to the graph edge selector: when the canvas
    has two outgoing edges labeled ``true`` / ``false``, the StateGraph
    ``add_conditional_edges`` reads ``branch`` and routes accordingly.
    """
    rendered = render_jinja(config.expression, inputs)
    # truthy check: explicit truthy strings, non-zero numbers, non-empty strings
    # (except the explicit falsy strings "false"/"0"/"no"/"").
    if rendered in ("true", "True", "1", "yes"):
        branch = True
    elif rendered in ("false", "False", "0", "no", ""):
        branch = False
    else:
        try:
            branch = bool(int(rendered))
        except ValueError:
            branch = bool(rendered) and rendered.lower() != "false"
    return {"branch": branch, "raw": str(rendered)}


__all__ = ["ConditionConfig", "ConditionNode", "condition_execute"]
