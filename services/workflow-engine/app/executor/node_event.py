"""Persist per-node execution events to the ``node_event`` table.

One row per state transition (``running`` / ``completed`` / ``failed``
/ ``skipped``). Used by:

- The workflow compiler (``app/graph/compiler.py``) to record every
  per-node transition (one row per state change).
- The SSE stream (``app/executor/sse.py``) to read rows back in
  ``id`` order and push them to the client.

The ``run_id`` column is a foreign key to ``workflow_run.run_id`` with
``ON DELETE CASCADE`` (see ``app/models/workflow.py``), so dropping a
run also drops its node history.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from app.database import SessionLocal
from app.models.workflow import NodeEvent


async def write_node_event(
    run_id: uuid.UUID | str,
    node_id: str,
    status: str,
    input_json: dict | None = None,
    output_json: dict | None = None,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    retry_count: int = 0,
    error_class: str | None = None,
    error_message: str | None = None,
) -> int:
    """Insert a ``node_event`` row. Returns the new event id.

    The ``started_at`` / ``ended_at`` defaults are filled in based on
    the ``status`` value so callers only need to set them explicitly
    for retry / re-issue scenarios.
    """
    now = datetime.utcnow()
    if started_at is None and status == "running":
        started_at = now
    if ended_at is None and status in ("completed", "failed", "skipped"):
        ended_at = now
    async with SessionLocal() as session:
        ev = NodeEvent(
            run_id=run_id,
            node_id=node_id,
            status=status,
            input_json=input_json,
            output_json=output_json,
            started_at=started_at,
            ended_at=ended_at,
            retry_count=retry_count,
            error_class=error_class,
            error_message=error_message,
        )
        session.add(ev)
        await session.commit()
        await session.refresh(ev)
        return ev.id


__all__ = ["write_node_event"]
