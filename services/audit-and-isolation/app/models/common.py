"""Cross-cutting Pydantic schemas shared between HTTP layer + dispatch.

* ``ModelKind`` is the typed enum for the ``X-Model-Kind`` header
  (``public`` ↔ open-source LLM provider, ``private`` ↔ internal
  vLLM endpoint).
* ``HeaderSchema`` is the validated header triple every inbound
  request must carry.
* ``ErrorResponse`` is the gateway's error body shape; FastAPI
  exception handlers serialise into this so callers see a uniform
  envelope.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ModelKind(str, Enum):
    """Discriminator for upstream family.

    ``str`` mixin lets the enum compare against raw strings — the
    routing dispatcher does ``entry["model_kind"] == header.model_kind.value``
    against plain string values, so the ``str`` mixin keeps the
    comparison symmetric (the .value side is enough in practice; the
    mixin also makes accidental equality checks like
    ``header.model_kind == "public"`` work as a programmer convenience).
    """

    PUBLIC = "public"
    PRIVATE = "private"


class HeaderSchema(BaseModel):
    """Validated header triple for ``POST /v1/chat/completions``.

    ``trace_id`` length bounds (8..128) match the gstack project-wide
    trace-id convention; too-short IDs are rejected to avoid collisions
    in the per-trace Redis namespace.
    """

    trace_id: str = Field(..., min_length=8, max_length=128)
    model_kind: ModelKind
    bypass_isolation: bool = False


class ErrorResponse(BaseModel):
    """Uniform error envelope. ``trace_id`` is included when the
    exception happened after the header was parsed (so the caller can
    cross-reference the gateway's audit_log row)."""

    error_class: str
    message: str
    trace_id: str | None = None


__all__ = ["ErrorResponse", "HeaderSchema", "ModelKind"]
