"""GET /v1/models — list the enabled models in the routing table.

The response shape mirrors OpenAI's ``/v1/models`` so a client
that already speaks the OpenAI SDK can iterate over the available
models without any custom code. We deliberately do *not* include
the upstream ``base_url`` / ``path`` in the response — those are
internal to the gateway and should never leak past the egress
boundary (the eng-review report flagged this as a tenant
separation requirement: an internal vLLM endpoint URL is
information only the gateway is allowed to know).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import select

from app.database import get_session
from app.models.audit import ModelRouting
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class ModelInfo(BaseModel):
    """OpenAI-shaped model descriptor — the only fields a client
    should ever need (id + ownership)."""

    id: str
    object: str = "model"
    created: int  # unix seconds
    owned_by: str  # "public" or "private"


class ModelList(BaseModel):
    """Top-level response body — matches OpenAI's ``/v1/models`` shape."""

    object: str = "list"
    data: list[ModelInfo]


@router.get("/models", response_model=ModelList)
async def list_models() -> ModelList:
    """Return the enabled models from ``model_routing``.

    The ``created`` timestamp is the row's ``updated_at`` (in
    unix seconds), which gives clients a stable, monotonic
    ordering signal that doesn't change unless a model is
    actually updated. We pick ``updated_at`` over ``id`` because
    a newer-model-restart scenario should bump the timestamp
    visibly to clients.
    """
    async with get_session() as s:
        result = await s.execute(
            select(ModelRouting).where(ModelRouting.enabled.is_(True))
        )
        rows = result.scalars().all()
    data: list[ModelInfo] = []
    for row in rows:
        updated = row.updated_at
        if updated is None:
            updated = datetime.now(timezone.utc)
        # SQLAlchemy returns naive datetimes for ``DateTime(timezone=True)``
        # columns served by some drivers; assume UTC if no tzinfo.
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        data.append(
            ModelInfo(
                id=row.model_name,
                created=int(updated.timestamp()),
                owned_by=row.model_kind,
            )
        )
    return ModelList(data=data)


__all__ = ["router"]
