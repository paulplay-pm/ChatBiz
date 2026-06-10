import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_session
from app.models.workflow import WorkflowDefinition
from app.errors.classes import SecurityError, UserError

router = APIRouter(prefix="/workflows", tags=["workflows"])


class CreateWorkflowRequest(BaseModel):
    name: str
    definition_json: dict


class UpdateWorkflowRequest(BaseModel):
    name: Optional[str] = None
    definition_json: Optional[dict] = None


def get_user_id(request: Request) -> str:
    """Extract user_id from request. MVP: header X-User-Id (V1.0: replace with IAM/JWT)."""
    uid = request.headers.get("X-User-Id")
    if not uid:
        raise UserError("缺少 X-User-Id header (MVP 阶段用 header 鉴权,V1.0 切 IAM)")
    return uid


@router.post("", status_code=201)
async def create_workflow(
    body: CreateWorkflowRequest,
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
):
    wf = WorkflowDefinition(
        id=uuid.uuid4(),
        version=1,
        name=body.name,
        created_by=user_id,
        definition_json=body.definition_json,
    )
    session.add(wf)
    await session.commit()
    await session.refresh(wf)
    return {"id": str(wf.id), "version": wf.version, "name": wf.name, "created_by": wf.created_by, "created_at": wf.created_at.isoformat()}


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: uuid.UUID,
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Return latest version of workflow_definition."""
    stmt = select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id).order_by(WorkflowDefinition.version.desc()).limit(1)
    wf = (await session.execute(stmt)).scalar_one_or_none()
    if wf is None or wf.archived:
        raise HTTPException(status_code=404, detail={"error_class": "user", "error_message": "工作流不存在"})
    if wf.created_by != user_id:
        raise SecurityError(f"无权访问工作流 {workflow_id}")
    return {"id": str(wf.id), "version": wf.version, "name": wf.name, "definition_json": wf.definition_json, "created_at": wf.created_at.isoformat()}


@router.get("/{workflow_id}/versions")
async def list_versions(
    workflow_id: uuid.UUID,
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
):
    """List all versions, newest first."""
    # Auth check on first version
    first = (await session.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id).order_by(WorkflowDefinition.version.asc()).limit(1)
    )).scalar_one_or_none()
    if first is None:
        raise HTTPException(status_code=404, detail={"error_class": "user", "error_message": "工作流不存在"})
    if first.created_by != user_id:
        raise SecurityError(f"无权访问工作流 {workflow_id}")
    all_versions = (await session.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id).order_by(WorkflowDefinition.version.desc())
    )).scalars().all()
    return {"versions": [{"version": v.version, "name": v.name, "created_at": v.created_at.isoformat(), "archived": v.archived} for v in all_versions]}


@router.get("/{workflow_id}/versions/{version}")
async def get_version(
    workflow_id: uuid.UUID,
    version: int,
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
):
    wf = await session.get(WorkflowDefinition, (workflow_id, version))
    if wf is None:
        raise HTTPException(status_code=404, detail={"error_class": "user", "error_message": f"工作流 {workflow_id} v{version} 不存在"})
    if wf.created_by != user_id:
        raise SecurityError(f"无权访问工作流 {workflow_id}")
    return {"id": str(wf.id), "version": wf.version, "name": wf.name, "definition_json": wf.definition_json}


@router.put("/{workflow_id}")
async def update_workflow(
    workflow_id: uuid.UUID,
    body: UpdateWorkflowRequest,
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Update creates a NEW version. Old versions preserved for rollback."""
    latest = (await session.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id).order_by(WorkflowDefinition.version.desc()).limit(1)
    )).scalar_one_or_none()
    if latest is None:
        raise HTTPException(status_code=404, detail={"error_class": "user", "error_message": "工作流不存在"})
    if latest.archived:
        raise UserError("工作流已 archived,不可更新")
    if latest.created_by != user_id:
        raise SecurityError(f"无权更新工作流 {workflow_id}")
    new_wf = WorkflowDefinition(
        id=workflow_id,
        version=latest.version + 1,
        name=body.name or latest.name,
        created_by=user_id,
        definition_json=body.definition_json or latest.definition_json,
    )
    session.add(new_wf)
    await session.commit()
    await session.refresh(new_wf)
    # Clear compile cache for this workflow
    from app.graph.compiler import clear_compile_cache
    clear_compile_cache()
    return {"id": str(new_wf.id), "version": new_wf.version, "name": new_wf.name}


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: uuid.UUID,
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Soft delete: sets archived=true on all versions."""
    all_versions = (await session.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id)
    )).scalars().all()
    if not all_versions:
        raise HTTPException(status_code=404, detail={"error_class": "user", "error_message": "工作流不存在"})
    if all_versions[0].created_by != user_id:
        raise SecurityError(f"无权删除工作流 {workflow_id}")
    for v in all_versions:
        v.archived = True
    await session.commit()
    return None
