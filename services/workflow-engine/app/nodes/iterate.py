"""Iterate node — fan out a sub-section over an array of items.

Reads the input array from ``inputs[input_array]`` and dispatches the
configured loop body once per item. For the MVP we just enumerate and
return the items + count; the real per-item dispatch (with concurrency
control + error_strategy handling) is wired in Phase 5 when the
StateGraph compiler lands.

The ``error_strategy`` field defines how per-item failures are handled:

* ``fail_fast`` (default) — first item failure aborts the whole iteration.
* ``skip`` — failed item is dropped from the result, others continue.
* ``continue`` — failed item is recorded with an ``error`` field, others continue.
"""
from __future__ import annotations

from pydantic import Field

from app.errors.classes import UserError
from app.nodes.contracts.base import BaseConfig, BaseNode
from app.nodes.registry import register


class IterateConfig(BaseConfig):
    """Configuration for the iterate node."""

    input_array: str = Field(..., description="inputs 中数组的 key 名 (e.g. 'orders')")
    concurrency: int = Field(1, ge=1, le=10, description="最大并发 (Phase 5 才生效)")
    error_strategy: str = Field(
        "fail_fast",
        description="fail_fast | skip | continue (Phase 5 才生效,MVP 仅校验字段)",
    )


@register("iterate", version="1.0.0")
class IterateNode(BaseNode):
    """Node contract for the iterate node."""

    config: IterateConfig


async def iterate_execute(config: IterateConfig, inputs: dict) -> dict:
    """Validate that ``input_array`` is a list; return the items + count.

    Raises ``UserError`` (boundary #3) if the referenced key is missing or
    not a list — this is a config-time failure, not a runtime failure.
    """
    arr = inputs.get(config.input_array)
    if not isinstance(arr, list):
        raise UserError(
            f"iterate 节点的 input_array={config.input_array!r} 必须是 list,"
            f"实际类型 {type(arr).__name__}"
        )
    # MVP stub: just enumerate. Phase 5 compiler will dispatch to a sub-graph
    # per item with the configured concurrency + error_strategy.
    return {"items": arr, "count": len(arr)}


__all__ = ["IterateConfig", "IterateNode", "iterate_execute"]
