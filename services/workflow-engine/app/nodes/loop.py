"""Loop node — execute a sub-section of the workflow N times until exit-condition is true.

This is the synchronous, in-graph loop primitive. For each iteration:

1. Render the ``exit_condition`` Jinja2 expression against the current state
   (augmented with ``_iteration`` index and ``_results`` accumulator).
2. If the condition is truthy, break.
3. Otherwise record the iteration in the ``_results`` accumulator and continue.

Phase 5 will replace this with a real LangGraph subgraph dispatch (the
current implementation only *records* iterations, it doesn't re-execute
the loop body — the loop body is a separate set of nodes on the canvas
that the compiler will wire into a subgraph). For the MVP we expose the
config + contract so the canvas frontend can render the loop body
visually, even if execution semantics are not yet fully wired.
"""
from __future__ import annotations

from pydantic import Field

from app.graph.jinja import render_jinja
from app.nodes.contracts.base import BaseConfig, BaseNode
from app.nodes.registry import register


class LoopConfig(BaseConfig):
    """Configuration for the loop node."""

    max_iterations: int = Field(10, ge=1, le=1000, description="最大迭代次数(防 runaway loop)")
    exit_condition: str = Field(
        ...,
        description="Jinja2 表达式,返回 truthy 时退出循环;上下文可用 _iteration / _results",
    )
    loop_body_inputs: list[str] = Field(
        default_factory=list,
        description="每次循环传入 loop body 的 input keys(空 = 全部 inputs)",
    )


@register("loop", version="1.0.0")
class LoopNode(BaseNode):
    """Node contract for the loop node."""

    config: LoopConfig


async def loop_execute(config: LoopConfig, inputs: dict) -> dict:
    """Iterate up to ``max_iterations`` times, breaking on truthy ``exit_condition``.

    Returns ``{iterations: [...], count: int}``. The Phase-5 compiler will
    dispatch each iteration's loop body as a subgraph; this MVP execute
    function only records the iteration metadata so the contract + schema
    are stable for the canvas frontend.
    """
    results: list[dict] = []
    for i in range(config.max_iterations):
        should_exit = render_jinja(
            config.exit_condition,
            {**inputs, "_iteration": i, "_results": results},
        )
        if should_exit in ("true", "True", "1", "yes"):
            break
        results.append(
            {"iteration": i, "inputs": {k: inputs.get(k) for k in config.loop_body_inputs}}
        )
    return {"iterations": results, "count": len(results)}


__all__ = ["LoopConfig", "LoopNode", "loop_execute"]
