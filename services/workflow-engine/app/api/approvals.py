import uuid
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models.workflow import Approval, WorkflowRun
from app.errors.classes import ApprovalNotFound, ApprovalAlreadyResponded, UnauthorizedApprovalAccess, UserError
from app.api.deps import get_user_id

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ResumeRequest(BaseModel):
    decision: str  # 'approved' | 'rejected'
    payload: dict = {}


@router.get("/pending")
async def list_pending(
    user: str,
    page: int = 1,
    page_size: int = 20,
    _user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
):
    """List pending approvals for a user. Auth enforced via shared dep."""
    if not user:
        raise UserError("缺少 user 查询参数")
    offset = (page - 1) * page_size
    stmt = select(Approval).where(
        Approval.approver_user_id == user, Approval.status == "pending"
    ).order_by(Approval.created_at.asc()).offset(offset).limit(page_size)
    approvals = (await session.execute(stmt)).scalars().all()
    total = (await session.execute(
        select(func.count(Approval.approval_id)).where(Approval.approver_user_id == user, Approval.status == "pending")
    )).scalar() or 0
    return {
        "approvals": [
            {
                "approval_id": str(a.approval_id),
                "run_id": str(a.run_id),
                "node_id": a.node_id,
                "approver_user_id": a.approver_user_id,
                "status": a.status,
                "created_at": a.created_at.isoformat(),
            }
            for a in approvals
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/{approval_id}:resume")
async def resume_approval(
    approval_id: uuid.UUID,
    body: ResumeRequest,
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
):
    ap = await session.get(Approval, approval_id)
    if ap is None:
        raise ApprovalNotFound(f"审批 {approval_id} 不存在")
    if ap.approver_user_id != user_id:
        raise UnauthorizedApprovalAccess(f"无权访问审批 {approval_id}")
    if ap.status != "pending":
        raise ApprovalAlreadyResponded(f"审批已 {ap.status},不可重复 resume")
    if body.decision not in ("approved", "rejected"):
        raise UserError(f"decision 必须是 'approved' 或 'rejected',得到 {body.decision!r}")
    ap.status = body.decision
    ap.responded_at = datetime.utcnow()
    ap.response_payload = body.payload
    await session.commit()
    # TODO: 真正续接 LangGraph thread (Phase 6.5 实施)
    return {"approval_id": str(approval_id), "status": ap.status, "responded_at": ap.responded_at.isoformat()}


@router.post("/{approval_id}:cancel")
async def cancel_approval(
    approval_id: uuid.UUID,
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
):
    ap = await session.get(Approval, approval_id)
    if ap is None:
        raise ApprovalNotFound(f"审批 {approval_id} 不存在")
    run = await session.get(WorkflowRun, ap.run_id)
    if run is None:
        raise UserError(f"workflow_run {ap.run_id} 不存在")
    # Allow approver OR workflow starter to cancel
    if ap.approver_user_id != user_id and run.started_by != user_id:
        raise UnauthorizedApprovalAccess(f"无权取消审批 {approval_id}")
    ap.status = "cancelled"
    ap.responded_at = datetime.utcnow()
    run.status = "cancelled"
    run.ended_at = datetime.utcnow()
    await session.commit()
    return {"approval_id": str(approval_id), "status": "cancelled"}
