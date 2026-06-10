"""Start node — the entry point of every workflow.

Marks the workflow as started and threads the initial inputs through. The
``inputs`` field is a freeform schema describing what the workflow expects at
start time — the canvas frontend uses it to render an input form for debug runs.
"""
from __future__ import annotations

from pydantic import Field

from app.nodes.contracts.base import BaseConfig, BaseNode
from app.nodes.registry import register


class StartConfig(BaseConfig):
    """Configuration for the start node."""

    inputs: dict = Field(
        default_factory=dict,
        description="Workflow start inputs schema (freeform for MVP, e.g. {month: str, dept: str})",
    )


@register("start", version="1.0.0")
class StartNode(BaseNode):
    """Node contract for the workflow entry point."""

    config: StartConfig


async def start_execute(config: StartConfig, inputs: dict) -> dict:
    """Pass-through: return the inputs under the ``received_inputs`` key plus a ``started`` flag.

    The ``started`` flag is used by the workflow runner to mark the run row as
    transitioning from PENDING to RUNNING — downstream nodes can rely on it being
    present in the state stream.
    """
    return {"started": True, "received_inputs": dict(inputs)}


__all__ = ["StartConfig", "StartNode", "start_execute"]
