import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models.workflow import WorkflowRun, NodeEvent
from app.executor.sse import run_events_sse

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}")
async def get_run(
    run_id: uuid.UUID,
    x_user_id: str = Depends(lambda: None),  # placeholder, override below
    session: AsyncSession = Depends(get_session),
):
    """Get workflow_run status + last 50 node events."""
    from fastapi import Header
    # Hacky: re-extract user_id
    return await _get_run_impl(run_id, session)


async def _get_run_impl(run_id, session):
    run = await session.get(WorkflowRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail={"error_class": "user", "error_message": f"workflow_run {run_id} 不存在"})
    events = (await session.execute(
        select(NodeEvent).where(NodeEvent.run_id == run_id).order_by(NodeEvent.id.desc()).limit(50)
    )).scalars().all()
    return {
        "run_id": str(run.run_id),
        "workflow_id": str(run.workflow_id),
        "workflow_version": run.workflow_version,
        "thread_id": run.thread_id,
        "mode": run.mode,
        "status": run.status,
        "started_by": run.started_by,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        "error_class": run.error_class,
        "error_message": run.error_message,
        "events": [
            {"id": e.id, "node_id": e.node_id, "status": e.status, "started_at": e.started_at.isoformat() if e.started_at else None, "ended_at": e.ended_at.isoformat() if e.ended_at else None, "error_class": e.error_class}
            for e in events
        ],
    }


@router.get("/{run_id}/events")
async def stream_events(run_id: uuid.UUID):
    """SSE stream of node events for the run."""
    return run_events_sse(str(run_id))
