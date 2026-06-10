"""Base Pydantic models shared by every Node Contract.

These are the *parent* classes for the 14 node types. Each concrete node module
(e.g. ``app/nodes/llm.py``) defines a ``BaseConfig`` subclass with typed fields,
then a ``BaseNode`` subclass wrapping that config. The registry's
``model_json_schema()`` call introspects the BaseNode to emit the 4 derived
products (UI config schema, I/O schema, LangGraph node function, validator).

Per the eng-review decision (Arch #2 + Quality #1): a single Pydantic BaseModel
is the source of truth. We deliberately keep ``input_schema`` and ``output_schema``
as freeform dicts at this level — the MVP doesn't need strict I/O typing because
the canvas frontend doesn't render them. Phase 5 will tighten this to typed
``model_json_schema()`` outputs once we know the actual data flow shapes from
running the paul 财务月报 workflow.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BaseConfig(BaseModel):
    """Common base for all node configs. Empty by default; nodes extend it.

    The ``extra="forbid"`` config prevents typo'd fields from being silently
    accepted (e.g. ``credentialID`` vs ``credential_id``) — the canvas save
    endpoint will return a 400 with a clear pydantic error message.
    """

    model_config = ConfigDict(extra="forbid")


class BaseNode(BaseModel):
    """Common base for node contract BaseModels.

    Each contract has a typed ``config`` field (a ``BaseConfig`` subclass) plus
    freeform ``input_schema`` / ``output_schema`` dicts. The actual schema
    generation is done by the registry via Pydantic introspection.
    """

    model_config = ConfigDict(extra="forbid")

    config: BaseConfig
    input_schema: dict = Field(
        default_factory=dict,
        description="Input type description (freeform for MVP, Phase 5 will type this)",
    )
    output_schema: dict = Field(
        default_factory=dict,
        description="Output type description (freeform for MVP, Phase 5 will type this)",
    )


__all__ = ["BaseConfig", "BaseNode"]
