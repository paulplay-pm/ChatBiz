"""Extract node — LLM-based structured extraction from free-form text.

Renders the ``source`` template (typically ``{{n2.output.content}}`` or
similar) to get the source text, then asks an LLM to extract structured
data matching the ``schema`` dict. For the MVP we only render the source
and return a stub — the real LLM call (with response_format=json_schema
or tool-use) is wired in Phase 5.

The ``schema`` field is intentionally freeform in the MVP because the
canvas frontend doesn't yet have a structured-schema editor; Phase 5
will type it as a JSON Schema dict + a ``mode`` field (``json_schema`` /
``function_calling``) for the LLM call.
"""
from __future__ import annotations

from pydantic import Field

from app.graph.jinja import render_jinja
from app.nodes.contracts.base import BaseConfig, BaseNode
from app.nodes.registry import register


class ExtractConfig(BaseConfig):
    """Configuration for the extract node."""

    source: str = Field(
        ...,
        description="Jinja2 path to source text, e.g. '{{n2.output.content}}'",
    )
    schema: dict = Field(
        ...,
        description="Extraction schema (freeform for MVP, Phase 5 will be JSON Schema)",
    )
    output_format: str = Field(
        "json",
        description="json | text — MVP 仅校验字段,Phase 5 实际传给 LLM response_format",
    )


@register("extract", version="1.0.0")
class ExtractNode(BaseNode):
    """Node contract for the extract node."""

    config: ExtractConfig


async def extract_execute(config: ExtractConfig, inputs: dict) -> dict:
    """Render the source template; return a stub for Phase 5 to replace with LLM call."""
    source_text = render_jinja(config.source, inputs)
    return {
        "source": source_text,
        "schema": config.schema,
        "extracted": None,
        "stub": True,
    }


__all__ = ["ExtractConfig", "ExtractNode", "extract_execute"]
