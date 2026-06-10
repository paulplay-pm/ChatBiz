"""End node — the terminal node of every workflow.

Returns a subset of the workflow state (selected by ``output_keys``) as the
final workflow result. If ``output_keys`` is empty, the entire input dict is
returned (useful for chatflow mode where the full state is the response).
"""
from __future__ import annotations

from pydantic import Field

from app.nodes.contracts.base import BaseConfig, BaseNode
from app.nodes.registry import register


class EndConfig(BaseConfig):
    """Configuration for the end node."""

    output_keys: list[str] = Field(
        default_factory=list,
        description="Which state keys to include in the final workflow output. Empty = all inputs.",
    )


@register("end", version="1.0.0")
class EndNode(BaseNode):
    """Node contract for the workflow terminal point."""

    config: EndConfig


async def end_execute(config: EndConfig, inputs: dict) -> dict:
    """Project the input dict to the configured ``output_keys`` (or pass-through if empty)."""
    if config.output_keys:
        return {k: inputs.get(k) for k in config.output_keys}
    return dict(inputs)


__all__ = ["EndConfig", "EndNode", "end_execute"]
