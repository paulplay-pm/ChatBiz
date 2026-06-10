"""Subflow node — invoke a child workflow as a sub-step of the parent.

The parent workflow references a ``sub_workflow_id`` (a workflow definition
already stored in the ``workflow_definitions`` table). The ``input_mapping``
and ``output_mapping`` fields define how to project the parent state into
the child workflow's inputs and the child's outputs back into the parent
state.

For the MVP we only validate the mapping shape and return a stub response;
the actual recursive invoke (with full state isolation) is wired in
Phase 5 once the workflow runner can fetch + compile child workflow
definitions on the fly.
"""
from __future__ import annotations

from pydantic import Field

from app.nodes.contracts.base import BaseConfig, BaseNode
from app.nodes.registry import register


class SubflowConfig(BaseConfig):
    """Configuration for the subflow node."""

    sub_workflow_id: str = Field(..., description="子工作流 ID (引用 workflow_definitions 表)")
    input_mapping: dict[str, str] = Field(
        default_factory=dict,
        description="父 → 子 input key 映射, e.g. {'parent_k': 'child_k'}",
    )
    output_mapping: dict[str, str] = Field(
        default_factory=dict,
        description="子 → 父 output key 映射, e.g. {'child_k': 'parent_k'}",
    )


@register("subflow", version="1.0.0")
class SubflowNode(BaseNode):
    """Node contract for the subflow node."""

    config: SubflowConfig


async def subflow_execute(config: SubflowConfig, inputs: dict) -> dict:
    """Project inputs through ``input_mapping``; return a stub for Phase 5 to replace.

    Real implementation will: (1) fetch the child workflow definition by id,
    (2) compile its StateGraph, (3) invoke it with the mapped inputs,
    (4) project the child outputs back through ``output_mapping``.
    """
    mapped_inputs = {
        child_key: inputs.get(parent_key)
        for parent_key, child_key in config.input_mapping.items()
    }
    return {
        "subflow_id": config.sub_workflow_id,
        "mapped_inputs": mapped_inputs,
        "stub": True,
    }


__all__ = ["SubflowConfig", "SubflowNode", "subflow_execute"]
