"""Server-Sent Events stream of node events for a workflow_run.

Backs the ``GET /api/runs/:id/events`` endpoint. The stream emits three
event families:

- ``node_running`` / ``node_completed`` / ``node_failed`` / ``node_skipped``
  per row in ``node_event`` (one event per row, in ``id`` order).
- ``run_completed`` / ``run_failed`` / ``run_cancelled`` as the terminal
  event when the ``workflow_run`` row reaches one of those statuses.
- ``error`` if the run id is not found (or the row was deleted mid-stream).

The implementation is a polling loop: it queries ``node_event`` for
rows with ``id > last_event_id`` every 500 ms and yields anything new.
Polling (vs. ``LISTEN``/``NOTIFY``) is a deliberate choice for MVP:
the postgres async driver doesn't ship NOTIFY support without
asyncpg-specific plumbing, and 500 ms latency is well within the
"operator watching a run start" UX budget. Phase 6 will swap to
``LISTEN``/``NOTIFY`` once we measure polling CPU at scale.
"""
from __future__ import annotations

import asyncio
import json

from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select

from app.database import SessionLocal
from app.models.workflow import NodeEvent, WorkflowRun

_POLL_INTERVAL_SECONDS = 0.5

# Run statuses that close the stream.
_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


async def run_events_sse(run_id: str):
    """SSE generator for one workflow run. Returns an ``EventSourceResponse``.

    Args:
        run_id: ``WorkflowRun.run_id`` as a string (UUID). The endpoint
            handler is responsible for parsing / validating this.

    Yields (via ``EventSourceResponse``):
        * ``node_<status>`` events for each new ``node_event`` row
        * ``run_<status>`` terminal event when the run reaches a
          final state
        * ``error`` event if the run id is not found
    """
    async def event_generator():
        last_event_id = 0

        # Sanity check: workflow_run must exist before we start streaming.
        async with SessionLocal() as session:
            run = await session.get(WorkflowRun, run_id)
            if run is None:
                yield {
                    "event": "error",
                    "data": json.dumps(
                        {"error": f"workflow_run {run_id} not found"}
                    ),
                }
                return

        while True:
            async with SessionLocal() as session:
                run = await session.get(WorkflowRun, run_id)
                if run is None:
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": "run deleted mid-stream"}),
                    }
                    return

                # Drain any new node_event rows in id order.
                stmt = (
                    select(NodeEvent)
                    .where(NodeEvent.run_id == run_id, NodeEvent.id > last_event_id)
                    .order_by(NodeEvent.id)
                )
                result = await session.execute(stmt)
                events = result.scalars().all()
                for ev in events:
                    last_event_id = ev.id
                    payload = {
                        "run_id": str(run_id),
                        "node_id": ev.node_id,
                        "status": ev.status,
                        "ts": ev.started_at.isoformat() if ev.started_at else None,
                    }
                    yield {"event": f"node_{ev.status}", "data": json.dumps(payload)}

                # Check for terminal run status; emit and close.
                if run.status in _TERMINAL_STATUSES:
                    yield {
                        "event": f"run_{run.status}",
                        "data": json.dumps(
                            {"run_id": str(run_id), "status": run.status}
                        ),
                    }
                    return

            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    return EventSourceResponse(event_generator())


__all__ = ["run_events_sse"]
