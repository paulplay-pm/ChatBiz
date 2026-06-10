import uuid
from typing import Literal, Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models.workflow import WorkflowDefinition, WorkflowRun
from app.errors.classes import SecurityError
from app.executor.runner import schedule_run
from app.executor.credential_check import check_credentials
from app.api.deps import get_user_id

router = APIRouter(prefix="/workflows", tags=["runs"])


class RunRequest(BaseModel):
    mode: Literal["workflow", "chatflow"] = "workflow"
    initial_inputs: dict = {}
    variables: dict = {}


@router.post("/{workflow_id}:run", status_code=202)
async def start_run(
    workflow_id: uuid.UUID,
    body: RunRequest,
    user_id: str = Depends(get_user_id),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    session: AsyncSession = Depends(get_session),
):
    """Start a workflow run asynchronously. Returns 202 + run_id."""
    latest = (await session.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id).order_by(WorkflowDefinition.version.desc()).limit(1)
    )).scalar_one_or_none()
    if latest is None or latest.archived:
        raise HTTPException(status_code=404, detail={"error_class": "user", "error_message": "工作流不存在"})
    if latest.created_by != user_id:
        raise SecurityError(f"无权启动工作流 {workflow_id}")

    # Pre-flight credential check
    await check_credentials(latest.definition_json, user_id)

    # Create workflow_run row first
    from app.graph.dispatcher import build_thread_id
    run = WorkflowRun(
        workflow_id=workflow_id,
        workflow_version=latest.version,
        thread_id=build_thread_id(body.mode, x_session_id),
        mode=body.mode,
        status="pending",
        started_by=user_id,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    # Schedule background execution
    definition = dict(latest.definition_json)
    definition["id"] = str(workflow_id)
    definition["version"] = latest.version
    # Inject variables
    if body.variables:
        definition.setdefault("variables", {}).update(body.variables)

    schedule_run(
        definition, body.mode, user_id,
        session_id=x_session_id, initial_state=body.initial_inputs,
    )
    return {"run_id": str(run.run_id), "status": "pending", "thread_id": run.thread_id}
