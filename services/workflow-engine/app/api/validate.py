import uuid
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models.workflow import WorkflowDefinition
from app.errors.classes import UserError
from sqlalchemy import select
from app.errors.cycle_detection import detect_cycle
from app.nodes.registry import NODE_REGISTRY

router = APIRouter(prefix="/workflows", tags=["workflows"])


def get_validate_user_id(request: Request) -> str:
    uid = request.headers.get("X-User-Id")
    if not uid:
        raise UserError("缺少 X-User-Id header")
    return uid


@router.post("/{workflow_id}/validate")
async def validate_workflow(
    workflow_id: uuid.UUID,
    request: Request,
    user_id: str = Depends(get_validate_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Validate a workflow definition for: (1) DAG cycles, (2) node type registration,
    (3) config schema validity, (4) Jinja2 syntax in conditions."""
    latest = (await session.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id).order_by(WorkflowDefinition.version.desc()).limit(1)
    )).scalar_one_or_none()
    if latest is None:
        raise UserError(f"工作流 {workflow_id} 不存在")
    if latest.created_by != user_id:
        from app.errors.classes import SecurityError
        raise SecurityError(f"无权访问工作流 {workflow_id}")

    definition = latest.definition_json
    errors = []

    # 1. Cycle detection
    try:
        cycle = detect_cycle(definition)
        if cycle:
            errors.append({"type": "cycle", "message": f"工作流存在物理循环: {' → '.join(cycle)}。请使用条件分支或循环节点而非物理循环", "edges": cycle})
    except Exception as e:
        errors.append({"type": "cycle_check_failed", "message": str(e)})

    # 2. Node type registration
    for n in definition.get("nodes", []):
        t = n.get("type")
        if t not in NODE_REGISTRY:
            errors.append({"type": "unknown_node_type", "node_id": n.get("id"), "message": f"节点类型 {t!r} 未注册。已注册类型: {list(NODE_REGISTRY.keys())}"})

    # 3. Config schema + 4. Jinja2 syntax
    from app.graph.jinja import render_jinja
    for n in definition.get("nodes", []):
        t = n.get("type")
        if t in NODE_REGISTRY:
            try:
                NODE_REGISTRY[t].validate_config(n.get("config", {}))
            except Exception as e:
                errors.append({"type": "config_invalid", "node_id": n.get("id"), "message": f"节点 {n.get('id')!r} config 验证失败: {e}"})
    for e in definition.get("edges", []):
        cond = e.get("condition")
        if cond:
            try:
                render_jinja(cond, {})
            except Exception as ex:
                errors.append({"type": "jinja_syntax", "edge": f"{e.get('from')}→{e.get('to')}", "message": f"边条件 Jinja2 语法错误: {ex}"})

    if errors:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail={"error_class": "user", "error_message": "工作流验证失败", "errors": errors})
    return {"valid": True, "node_count": len(definition.get("nodes", [])), "edge_count": len(definition.get("edges", []))}
