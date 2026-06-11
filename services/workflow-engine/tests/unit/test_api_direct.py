"""Direct-invocation tests for app/api/* endpoints to maximize line coverage.

ASGI client tests have known coverage-tracking gaps because ASGITransport +
LifespanManager wrap the app in contexts the coverage plugin doesn't always
attach to. Calling the endpoint function directly with a session is the
canonical way to ensure every branch is hit.
"""
import os

# Set required env vars BEFORE importing app.* modules.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("AUDIT_ISOLATION_URL", "http://audit-and-isolation-test:8080")
os.environ.setdefault("CREDENTIAL_SERVICE_URL", "http://credential-test:8000")
os.environ.setdefault("KNOWLEDGE_BASE_URL", "http://knowledge-base-test:8002")
os.environ.setdefault("AGENT_RUNTIME_URL", "http://agent-runtime-test:8003")
os.environ.setdefault("WORKFLOW_ENGINE_SERVICE_TOKEN", "test-token")
os.environ.setdefault("WECOM_WEBHOOK_URL", "")
os.environ.setdefault("DOCKER_SANDBOX_ENABLED", "false")
os.environ.setdefault("ENVIRONMENT", "test")

import asyncio
import uuid
import pytest
import respx
from httpx import Response

from app.errors.classes import (
    ChatBizError, SecurityError, UserError, WorkflowRuntimeError,
)


# ---------------------------------------------------------------------------
# Local cron_db fixture — rebinds cron + DB SessionLocal to the test engine.
# Mirrors the one in test_cron_and_misc.py and test_phase3_coverage.py.
# ---------------------------------------------------------------------------


@pytest.fixture
async def cron_db(db_setup, monkeypatch):
    """Patch app.database.SessionLocal + all module-level SessionLocal refs to db_setup's engine.

    Also drops + recreates the ``node_event`` table with a SQLite-friendly
    Integer id column (BigInteger autoincrement is not honored on SQLite by
    SQLAlchemy's default dialect). Production PostgreSQL is unaffected.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    from sqlalchemy import Integer, Table, MetaData, Column
    import app.database as dbmod
    from app.cron import approval_timeout, cleanup
    from app.executor import runner, node_event, sse

    md = MetaData()
    async with db_setup.begin() as conn:
        await conn.run_sync(md.reflect, only=["node_event", "workflow_run"])
    async with db_setup.begin() as conn:
        await conn.run_sync(md.tables["node_event"].drop, checkfirst=True)
        new_ne = Table(
            "node_event",
            MetaData(),
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("run_id", md.tables["workflow_run"].c.run_id.type, nullable=False),
            Column("node_id", md.tables["node_event"].c.node_id.type, nullable=False),
            Column("status", md.tables["node_event"].c.status.type, nullable=False),
            Column("input_json", md.tables["node_event"].c.input_json.type, nullable=True),
            Column("output_json", md.tables["node_event"].c.output_json.type, nullable=True),
            Column("started_at", md.tables["node_event"].c.started_at.type, nullable=True),
            Column("ended_at", md.tables["node_event"].c.ended_at.type, nullable=True),
            Column("retry_count", md.tables["node_event"].c.retry_count.type, nullable=False),
            Column("error_class", md.tables["node_event"].c.error_class.type, nullable=True),
            Column("error_message", md.tables["node_event"].c.error_message.type, nullable=True),
        )
        await conn.run_sync(new_ne.create)

    TestSession = async_sessionmaker(db_setup, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr(dbmod, "SessionLocal", TestSession)
    monkeypatch.setattr(approval_timeout, "SessionLocal", TestSession)
    monkeypatch.setattr(cleanup, "SessionLocal", TestSession)
    monkeypatch.setattr(runner, "SessionLocal", TestSession)
    monkeypatch.setattr(node_event, "SessionLocal", TestSession)
    monkeypatch.setattr(sse, "SessionLocal", TestSession)
    return TestSession


# ---------------------------------------------------------------------------
# app/api/validate.py — direct calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_direct_happy_path(cron_db, db_setup):
    from app.api.validate import validate_workflow
    from app.models.workflow import WorkflowDefinition

    Session = cron_db
    wf_id = uuid.uuid4()
    good = {
        "nodes": [
            {"id": "a", "type": "start", "config": {"inputs": {}}, "input_schema": {}, "output_schema": {}},
            {"id": "b", "type": "end", "config": {"output_keys": []}, "input_schema": {}, "output_schema": {}},
        ],
        "edges": [{"from": "a", "to": "b"}],
    }
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user", definition_json=good))
        await s.commit()
    async with Session() as s:
        result = await validate_workflow(wf_id, user_id="test-user", session=s)
    assert result["valid"] is True
    assert result["node_count"] == 2
    assert result["edge_count"] == 1


@pytest.mark.asyncio
async def test_validate_direct_not_found_raises(cron_db, db_setup):
    from app.api.validate import validate_workflow
    async with cron_db() as s:
        with pytest.raises(UserError, match="不存在"):
            await validate_workflow(uuid.uuid4(), user_id="test-user", session=s)


@pytest.mark.asyncio
async def test_validate_direct_cross_user_raises_security(cron_db, db_setup):
    from app.api.validate import validate_workflow
    from app.models.workflow import WorkflowDefinition
    Session = cron_db
    wf_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowDefinition(
            id=wf_id, version=1, name="t", created_by="other-user",
            definition_json={"nodes": [], "edges": []},
        ))
        await s.commit()
    async with Session() as s:
        with pytest.raises(SecurityError, match="无权访问"):
            await validate_workflow(wf_id, user_id="test-user", session=s)


@pytest.mark.asyncio
async def test_validate_direct_cycle_detected(cron_db, db_setup):
    from app.api.validate import validate_workflow
    from app.models.workflow import WorkflowDefinition
    from fastapi import HTTPException
    Session = cron_db
    wf_id = uuid.uuid4()
    bad = {
        "nodes": [
            {"id": "a", "type": "start", "config": {"inputs": {}}, "input_schema": {}, "output_schema": {}},
            {"id": "b", "type": "end", "config": {"output_keys": []}, "input_schema": {}, "output_schema": {}},
        ],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}],
    }
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user", definition_json=bad))
        await s.commit()
    async with Session() as s:
        with pytest.raises(HTTPException) as exc_info:
            await validate_workflow(wf_id, user_id="test-user", session=s)
    assert exc_info.value.status_code == 422
    body = exc_info.value.detail
    assert body["error_class"] == "user"
    assert any(e["type"] in ("cycle", "cycle_check_failed") for e in body["errors"])


@pytest.mark.asyncio
async def test_validate_direct_unknown_node_type(cron_db, db_setup):
    from app.api.validate import validate_workflow
    from app.models.workflow import WorkflowDefinition
    from fastapi import HTTPException
    Session = cron_db
    wf_id = uuid.uuid4()
    bad = {
        "nodes": [{"id": "x", "type": "totally_made_up", "config": {}}],
        "edges": [],
    }
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user", definition_json=bad))
        await s.commit()
    async with Session() as s:
        with pytest.raises(HTTPException) as exc_info:
            await validate_workflow(wf_id, user_id="test-user", session=s)
    assert any(e["type"] == "unknown_node_type" for e in exc_info.value.detail["errors"])


@pytest.mark.asyncio
async def test_validate_direct_config_invalid(cron_db, db_setup):
    from app.api.validate import validate_workflow
    from app.models.workflow import WorkflowDefinition
    from fastapi import HTTPException
    Session = cron_db
    wf_id = uuid.uuid4()
    # Valid node type, but config missing required field (e.g. start node
    # needs ``config.inputs`` — empty dict is fine, but let's pass extra
    # fields that BaseConfig rejects with extra='forbid').
    bad = {
        "nodes": [
            {"id": "a", "type": "start", "config": {"unknown_field": True}, "input_schema": {}, "output_schema": {}},
        ],
        "edges": [],
    }
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user", definition_json=bad))
        await s.commit()
    async with Session() as s:
        with pytest.raises(HTTPException) as exc_info:
            await validate_workflow(wf_id, user_id="test-user", session=s)
    assert any(e["type"] == "config_invalid" for e in exc_info.value.detail["errors"])


@pytest.mark.asyncio
async def test_validate_direct_jinja_syntax_error(cron_db, db_setup):
    from app.api.validate import validate_workflow
    from app.models.workflow import WorkflowDefinition
    from fastapi import HTTPException
    Session = cron_db
    wf_id = uuid.uuid4()
    bad = {
        "nodes": [
            {"id": "a", "type": "start", "config": {"inputs": {}}, "input_schema": {}, "output_schema": {}},
            {"id": "b", "type": "end", "config": {"output_keys": []}, "input_schema": {}, "output_schema": {}},
        ],
        "edges": [{"from": "a", "to": "b", "condition": "{{ unclosed jinja"}],
    }
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user", definition_json=bad))
        await s.commit()
    async with Session() as s:
        with pytest.raises(HTTPException) as exc_info:
            await validate_workflow(wf_id, user_id="test-user", session=s)
    assert any(e["type"] == "jinja_syntax" for e in exc_info.value.detail["errors"])


# ---------------------------------------------------------------------------
# app/api/workflows.py — direct calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflows_create_direct(cron_db, db_setup):
    from app.api.workflows import create_workflow, CreateWorkflowRequest
    Session = cron_db
    body = CreateWorkflowRequest(name="t", definition_json={"nodes": [], "edges": []})
    async with Session() as s:
        result = await create_workflow(body=body, user_id="test-user", session=s)
    assert "id" in result
    assert result["version"] == 1
    assert result["name"] == "t"
    assert result["created_by"] == "test-user"


@pytest.mark.asyncio
async def test_workflows_get_direct(cron_db, db_setup):
    from app.api.workflows import get_workflow
    from app.models.workflow import WorkflowDefinition
    Session = cron_db
    wf_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user",
                                 definition_json={"nodes": [], "edges": []}))
        await s.commit()
    async with Session() as s:
        result = await get_workflow(wf_id, user_id="test-user", session=s)
    assert result["name"] == "t"
    assert result["definition_json"] == {"nodes": [], "edges": []}


@pytest.mark.asyncio
async def test_workflows_get_not_found(cron_db, db_setup):
    from app.api.workflows import get_workflow
    from fastapi import HTTPException
    async with cron_db() as s:
        with pytest.raises(HTTPException) as exc:
            await get_workflow(uuid.uuid4(), user_id="test-user", session=s)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_workflows_get_archived_returns_404(cron_db, db_setup):
    from app.api.workflows import get_workflow
    from app.models.workflow import WorkflowDefinition
    from fastapi import HTTPException
    Session = cron_db
    wf_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user",
                                 definition_json={}, archived=True))
        await s.commit()
    async with Session() as s:
        with pytest.raises(HTTPException) as exc:
            await get_workflow(wf_id, user_id="test-user", session=s)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_workflows_get_cross_user_security(cron_db, db_setup):
    from app.api.workflows import get_workflow
    from app.models.workflow import WorkflowDefinition
    Session = cron_db
    wf_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="other-user",
                                 definition_json={}))
        await s.commit()
    async with Session() as s:
        with pytest.raises(SecurityError):
            await get_workflow(wf_id, user_id="test-user", session=s)


@pytest.mark.asyncio
async def test_workflows_list_versions_direct(cron_db, db_setup):
    from app.api.workflows import list_versions
    from app.models.workflow import WorkflowDefinition
    Session = cron_db
    wf_id = uuid.uuid4()
    async with Session() as s:
        for v in (1, 2, 3):
            s.add(WorkflowDefinition(id=wf_id, version=v, name=f"v{v}", created_by="test-user", definition_json={}))
        await s.commit()
    async with Session() as s:
        result = await list_versions(wf_id, user_id="test-user", session=s)
    assert len(result["versions"]) == 3
    assert result["versions"][0]["version"] == 3


@pytest.mark.asyncio
async def test_workflows_list_versions_not_found(cron_db, db_setup):
    from app.api.workflows import list_versions
    from fastapi import HTTPException
    async with cron_db() as s:
        with pytest.raises(HTTPException) as exc:
            await list_versions(uuid.uuid4(), user_id="test-user", session=s)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_workflows_list_versions_cross_user(cron_db, db_setup):
    from app.api.workflows import list_versions
    from app.models.workflow import WorkflowDefinition
    Session = cron_db
    wf_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="other-user", definition_json={}))
        await s.commit()
    async with Session() as s:
        with pytest.raises(SecurityError):
            await list_versions(wf_id, user_id="test-user", session=s)


@pytest.mark.asyncio
async def test_workflows_get_version_direct(cron_db, db_setup):
    from app.api.workflows import get_version
    from app.models.workflow import WorkflowDefinition
    Session = cron_db
    wf_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="v1", created_by="test-user", definition_json={"a": 1}))
        s.add(WorkflowDefinition(id=wf_id, version=2, name="v2", created_by="test-user", definition_json={"a": 2}))
        await s.commit()
    async with Session() as s:
        result = await get_version(wf_id, version=1, user_id="test-user", session=s)
    assert result["version"] == 1
    assert result["definition_json"] == {"a": 1}


@pytest.mark.asyncio
async def test_workflows_get_version_not_found(cron_db, db_setup):
    from app.api.workflows import get_version
    from fastapi import HTTPException
    async with cron_db() as s:
        with pytest.raises(HTTPException) as exc:
            await get_version(uuid.uuid4(), version=99, user_id="test-user", session=s)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_workflows_get_version_cross_user(cron_db, db_setup):
    from app.api.workflows import get_version
    from app.models.workflow import WorkflowDefinition
    Session = cron_db
    wf_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="other-user", definition_json={}))
        await s.commit()
    async with Session() as s:
        with pytest.raises(SecurityError):
            await get_version(wf_id, version=1, user_id="test-user", session=s)


@pytest.mark.asyncio
async def test_workflows_update_direct(cron_db, db_setup):
    from app.api.workflows import update_workflow, UpdateWorkflowRequest
    from app.models.workflow import WorkflowDefinition
    Session = cron_db
    wf_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="v1", created_by="test-user",
                                 definition_json={"old": True}))
        await s.commit()
    body = UpdateWorkflowRequest(name=None, definition_json={"new": True})
    async with Session() as s:
        result = await update_workflow(wf_id, body=body, user_id="test-user", session=s)
    assert result["version"] == 2


@pytest.mark.asyncio
async def test_workflows_update_not_found(cron_db, db_setup):
    from app.api.workflows import update_workflow, UpdateWorkflowRequest
    from fastapi import HTTPException
    body = UpdateWorkflowRequest()
    async with cron_db() as s:
        with pytest.raises(HTTPException) as exc:
            await update_workflow(uuid.uuid4(), body=body, user_id="test-user", session=s)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_workflows_update_archived_raises_user(cron_db, db_setup):
    from app.api.workflows import update_workflow, UpdateWorkflowRequest
    from app.models.workflow import WorkflowDefinition
    Session = cron_db
    wf_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user",
                                 definition_json={}, archived=True))
        await s.commit()
    body = UpdateWorkflowRequest()
    async with Session() as s:
        with pytest.raises(UserError, match="archived"):
            await update_workflow(wf_id, body=body, user_id="test-user", session=s)


@pytest.mark.asyncio
async def test_workflows_update_cross_user_security(cron_db, db_setup):
    from app.api.workflows import update_workflow, UpdateWorkflowRequest
    from app.models.workflow import WorkflowDefinition
    Session = cron_db
    wf_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="other-user", definition_json={}))
        await s.commit()
    body = UpdateWorkflowRequest()
    async with Session() as s:
        with pytest.raises(SecurityError):
            await update_workflow(wf_id, body=body, user_id="test-user", session=s)


@pytest.mark.asyncio
async def test_workflows_delete_direct(cron_db, db_setup):
    from app.api.workflows import delete_workflow
    from app.models.workflow import WorkflowDefinition
    Session = cron_db
    wf_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user", definition_json={}))
        await s.commit()
    async with Session() as s:
        result = await delete_workflow(wf_id, user_id="test-user", session=s)
    assert result is None
    async with Session() as s:
        wf = await s.get(WorkflowDefinition, (wf_id, 1))
        assert wf is not None
        assert wf.archived is True


@pytest.mark.asyncio
async def test_workflows_delete_not_found(cron_db, db_setup):
    from app.api.workflows import delete_workflow
    from fastapi import HTTPException
    async with cron_db() as s:
        with pytest.raises(HTTPException) as exc:
            await delete_workflow(uuid.uuid4(), user_id="test-user", session=s)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_workflows_delete_cross_user_security(cron_db, db_setup):
    from app.api.workflows import delete_workflow
    from app.models.workflow import WorkflowDefinition
    Session = cron_db
    wf_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="other-user", definition_json={}))
        await s.commit()
    async with Session() as s:
        with pytest.raises(SecurityError):
            await delete_workflow(wf_id, user_id="test-user", session=s)


# ---------------------------------------------------------------------------
# app/api/approvals.py — direct calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approvals_list_pending_missing_user_param(cron_db, db_setup):
    """list_pending with empty user string → UserError."""
    from app.api.approvals import list_pending
    with pytest.raises(UserError, match="缺少 user"):
        await list_pending(user="", page=1, page_size=20, _user_id="test-user", session=None)  # session unused for raise


@pytest.mark.asyncio
async def test_approvals_resume_not_found(cron_db, db_setup):
    from app.api.approvals import resume_approval, ResumeRequest
    async with cron_db() as s:
        with pytest.raises(UserError, match="不存在"):
            await resume_approval(uuid.uuid4(), body=ResumeRequest(decision="approved"), user_id="test-user", session=s)


@pytest.mark.asyncio
async def test_approvals_resume_cross_user_raises_security(cron_db, db_setup):
    from app.api.approvals import resume_approval, ResumeRequest
    from app.models.workflow import Approval, WorkflowRun
    Session = cron_db
    run_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowRun(run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1,
                          thread_id="t", mode="workflow", status="paused", started_by="u-other"))
        ap = Approval(run_id=run_id, node_id="n1", approver_user_id="u-other", status="pending")
        s.add(ap)
        await s.commit()
        ap_id = ap.approval_id
    async with Session() as s:
        with pytest.raises(SecurityError):
            await resume_approval(ap_id, body=ResumeRequest(decision="approved"), user_id="test-user", session=s)


@pytest.mark.asyncio
async def test_approvals_resume_invalid_decision_raises(cron_db, db_setup):
    from app.api.approvals import resume_approval, ResumeRequest
    from app.models.workflow import Approval, WorkflowRun
    Session = cron_db
    run_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowRun(run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1,
                          thread_id="t", mode="workflow", status="paused", started_by="test-user"))
        ap = Approval(run_id=run_id, node_id="n1", approver_user_id="test-user", status="pending")
        s.add(ap)
        await s.commit()
        ap_id = ap.approval_id
    async with Session() as s:
        with pytest.raises(UserError, match="decision 必须是"):
            await resume_approval(ap_id, body=ResumeRequest(decision="weird"), user_id="test-user", session=s)


@pytest.mark.asyncio
async def test_approvals_resume_already_responded_raises(cron_db, db_setup):
    from app.api.approvals import resume_approval, ResumeRequest
    from app.models.workflow import Approval, WorkflowRun
    Session = cron_db
    run_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowRun(run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1,
                          thread_id="t", mode="workflow", status="paused", started_by="test-user"))
        ap = Approval(run_id=run_id, node_id="n1", approver_user_id="test-user", status="approved")
        s.add(ap)
        await s.commit()
        ap_id = ap.approval_id
    async with Session() as s:
        with pytest.raises(UserError, match="不可重复"):
            await resume_approval(ap_id, body=ResumeRequest(decision="approved"), user_id="test-user", session=s)


@pytest.mark.asyncio
async def test_approvals_cancel_not_found(cron_db, db_setup):
    from app.api.approvals import cancel_approval
    async with cron_db() as s:
        with pytest.raises(UserError, match="不存在"):
            await cancel_approval(uuid.uuid4(), user_id="test-user", session=s)


@pytest.mark.asyncio
async def test_approvals_cancel_workflow_run_not_found(cron_db, db_setup):
    """Approval exists but its workflow_run was deleted → UserError."""
    from app.api.approvals import cancel_approval
    from app.models.workflow import Approval
    Session = cron_db
    run_id = uuid.uuid4()
    async with Session() as s:
        ap = Approval(run_id=run_id, node_id="n1", approver_user_id="test-user", status="pending")
        s.add(ap)
        await s.commit()
        ap_id = ap.approval_id
    async with Session() as s:
        with pytest.raises(UserError, match="workflow_run"):
            await cancel_approval(ap_id, user_id="test-user", session=s)


@pytest.mark.asyncio
async def test_approvals_cancel_unauthorized(cron_db, db_setup):
    from app.api.approvals import cancel_approval
    from app.models.workflow import Approval, WorkflowRun
    Session = cron_db
    run_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowRun(run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1,
                          thread_id="t", mode="workflow", status="paused", started_by="u-other"))
        ap = Approval(run_id=run_id, node_id="n1", approver_user_id="u-other", status="pending")
        s.add(ap)
        await s.commit()
        ap_id = ap.approval_id
    async with Session() as s:
        with pytest.raises(SecurityError):
            await cancel_approval(ap_id, user_id="test-user", session=s)


@pytest.mark.asyncio
async def test_approvals_cancel_by_approver(cron_db, db_setup):
    """The approver themselves can cancel (in addition to the workflow starter)."""
    from app.api.approvals import cancel_approval
    from app.models.workflow import Approval, WorkflowRun
    Session = cron_db
    run_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowRun(run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1,
                          thread_id="t", mode="workflow", status="paused", started_by="u-other"))
        ap = Approval(run_id=run_id, node_id="n1", approver_user_id="test-user", status="pending")
        s.add(ap)
        await s.commit()
        ap_id = ap.approval_id
    async with Session() as s:
        result = await cancel_approval(ap_id, user_id="test-user", session=s)
    assert result["status"] == "cancelled"


# ---------------------------------------------------------------------------
# app/api/run.py — direct calls (excludes the credential check path which
# needs respx mock).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_run_direct_happy_path(cron_db, db_setup):
    from app.api.run import start_run, RunRequest
    from app.models.workflow import WorkflowDefinition
    respx.get("http://credential-test:8000/v1/credentials/cred-Y/access").mock(
        return_value=Response(200, json={"allowed": True})
    )
    Session = cron_db
    wf_id = uuid.uuid4()
    defn = {
        "nodes": [{"id": "n1", "type": "llm", "config": {"credential_id": "cred-Y", "model": "gpt-4", "prompt": "hi"}}],
        "edges": [],
    }
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user", definition_json=defn))
        await s.commit()
    body = RunRequest(mode="workflow", initial_inputs={"k": "v"}, variables={"month": "2026-05"})
    async with Session() as s:
        result = await start_run(wf_id, body=body, user_id="test-user", x_session_id=None, session=s)
    assert "run_id" in result
    assert result["status"] == "pending"


@pytest.mark.asyncio
async def test_run_direct_not_found(cron_db, db_setup):
    from app.api.run import start_run, RunRequest
    from fastapi import HTTPException
    body = RunRequest()
    async with cron_db() as s:
        with pytest.raises(HTTPException) as exc:
            await start_run(uuid.uuid4(), body=body, user_id="test-user", x_session_id=None, session=s)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_run_direct_archived_404(cron_db, db_setup):
    from app.api.run import start_run, RunRequest
    from app.models.workflow import WorkflowDefinition
    from fastapi import HTTPException
    Session = cron_db
    wf_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user",
                                 definition_json={"nodes": [], "edges": []}, archived=True))
        await s.commit()
    body = RunRequest()
    async with Session() as s:
        with pytest.raises(HTTPException) as exc:
            await start_run(wf_id, body=body, user_id="test-user", x_session_id=None, session=s)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_run_direct_cross_user_security(cron_db, db_setup):
    from app.api.run import start_run, RunRequest
    from app.models.workflow import WorkflowDefinition
    Session = cron_db
    wf_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="other-user",
                                 definition_json={"nodes": [], "edges": []}))
        await s.commit()
    body = RunRequest()
    async with Session() as s:
        with pytest.raises(SecurityError):
            await start_run(wf_id, body=body, user_id="test-user", x_session_id=None, session=s)


# ---------------------------------------------------------------------------
# app/api/runs.py — direct calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runs_get_run_direct(cron_db, db_setup):
    from app.api.runs import get_run
    from app.models.workflow import WorkflowRun
    Session = cron_db
    run_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowRun(run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1,
                          thread_id="t", mode="workflow", status="completed", started_by="test-user"))
        await s.commit()
    async with Session() as s:
        result = await get_run(run_id, user_id="test-user", session=s)
    assert result["status"] == "completed"
    assert result["events"] == []


@pytest.mark.asyncio
async def test_runs_get_run_cross_user(cron_db, db_setup):
    from app.api.runs import get_run
    from app.models.workflow import WorkflowRun
    Session = cron_db
    run_id = uuid.uuid4()
    async with Session() as s:
        s.add(WorkflowRun(run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1,
                          thread_id="t", mode="workflow", status="running", started_by="u-other"))
        await s.commit()
    async with Session() as s:
        with pytest.raises(SecurityError):
            await get_run(run_id, user_id="test-user", session=s)


@pytest.mark.asyncio
async def test_runs_get_run_not_found(cron_db, db_setup):
    from app.api.runs import get_run
    from fastapi import HTTPException
    async with cron_db() as s:
        with pytest.raises(HTTPException) as exc:
            await get_run(uuid.uuid4(), user_id="test-user", session=s)
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# app/api/health.py — direct calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_healthz_direct(cron_db, db_setup):
    from app.api.health import healthz
    assert await healthz() == {"status": "ok"}


@pytest.mark.asyncio
@respx.mock
async def test_readyz_all_ok(cron_db, db_setup):
    from app.api.health import readyz
    import app.database as dbmod
    import fakeredis.aioredis
    import app.redis_client as rcm
    # Patch the real engine + redis so SELECT 1 / PING succeed.
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    rcm.get_redis = lambda: fake
    try:
        respx.get("http://audit-and-isolation-test:8080/healthz").mock(return_value=Response(200))
        respx.get("http://credential-test:8000/healthz").mock(return_value=Response(200))
        result = await readyz()
        assert result["status"] == "ready"
        assert result["checks"]["postgres"] == "ok"
        assert result["checks"]["redis"] == "ok"
        assert result["checks"]["audit_isolation"] == "ok"
        assert result["checks"]["credential"] == "ok"
    finally:
        await fake.aclose()


@pytest.mark.asyncio
async def test_readyz_postgres_down(cron_db, db_setup):
    """If the postgres query raises, the check reports 'down: ...'."""
    from app.api.health import readyz
    import app.api.health as health_mod

    class _BrokenConn:
        async def __aenter__(self):
            raise RuntimeError("postgres down")

        async def __aexit__(self, *args):
            return False

    class _BrokenEngine:
        def connect(self):
            return _BrokenConn()

    original = health_mod.engine
    health_mod.engine = _BrokenEngine()
    try:
        result = await readyz()
        assert "down" in result["checks"]["postgres"]
        assert result["status"] == "not_ready"
    finally:
        health_mod.engine = original


@pytest.mark.asyncio
@respx.mock
async def test_readyz_redis_down(cron_db, db_setup):
    from app.api.health import readyz
    import app.redis_client as rcm
    original = rcm.get_redis

    class _BrokenRedis:
        async def ping(self):
            raise RuntimeError("redis down")

    rcm.get_redis = lambda: _BrokenRedis()
    try:
        respx.get("http://audit-and-isolation-test:8080/healthz").mock(return_value=Response(200))
        respx.get("http://credential-test:8000/healthz").mock(return_value=Response(200))
        result = await readyz()
        assert "down" in result["checks"]["redis"]
    finally:
        rcm.get_redis = original


@pytest.mark.asyncio
@respx.mock
async def test_readyz_audit_http_error(cron_db, db_setup):
    """Audit returns 500 → check reports 'down: HTTP 500'."""
    from app.api.health import readyz
    respx.get("http://audit-and-isolation-test:8080/healthz").mock(return_value=Response(500))
    respx.get("http://credential-test:8000/healthz").mock(return_value=Response(200))
    result = await readyz()
    assert "down" in result["checks"]["audit_isolation"]


@pytest.mark.asyncio
@respx.mock
async def test_readyz_credential_http_error(cron_db, db_setup):
    from app.api.health import readyz
    respx.get("http://audit-and-isolation-test:8080/healthz").mock(return_value=Response(200))
    respx.get("http://credential-test:8000/healthz").mock(return_value=Response(500))
    result = await readyz()
    assert "down" in result["checks"]["credential"]


# ---------------------------------------------------------------------------
# app/api/nodes.py — direct calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nodes_list_direct(cron_db, db_setup):
    from app.api.nodes import list_node_types
    result = await list_node_types(_user_id="test-user")
    types = {nt["type"] for nt in result["node_types"]}
    assert len(types) == 14


@pytest.mark.asyncio
async def test_nodes_get_schema_direct(cron_db, db_setup):
    from app.api.nodes import get_node_schema
    result = await get_node_schema("llm", _user_id="test-user")
    assert result["type"] == "llm"
    assert "config_schema" in result


@pytest.mark.asyncio
async def test_nodes_get_schema_unknown(cron_db, db_setup):
    from app.api.nodes import get_node_schema
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await get_node_schema("nope", _user_id="test-user")
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# app/api/deps.py — direct calls (JWT path + 401)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# app/api/deps.py — uses ASGI (FastAPI dep injection needs a real Request)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deps_get_user_id_from_x_user_id(client):
    r = await client.get("/healthz", headers={"X-User-Id": "alice"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_deps_get_user_id_from_jwt(client):
    """A valid JWT (no signature check) decodes the sub claim."""
    import jwt as _jwt
    token = _jwt.encode({"sub": "user-from-jwt"}, "secret", algorithm="HS256")
    r = await client.get("/healthz", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_deps_get_user_id_jwt_missing_sub(client):
    """JWT decodes but has no 'sub' claim → 401 security."""
    import jwt as _jwt
    token = _jwt.encode({"foo": "bar"}, "secret", algorithm="HS256")
    r = await client.get("/api/nodes", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    body = r.json()
    # FastAPI wraps HTTPException in {"detail": ...}; chatbiz middleware unwraps
    # ChatBizError but HTTPException raised by get_user_id is not a ChatBizError.
    assert body.get("error_class") == "security" or body.get("detail", {}).get("error_class") == "security"


@pytest.mark.asyncio
async def test_deps_get_user_id_jwt_invalid(client):
    """Malformed JWT → 401 security."""
    r = await client.get("/api/nodes", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401
    body = r.json()
    assert body.get("error_class") == "security" or body.get("detail", {}).get("error_class") == "security"


@pytest.mark.asyncio
async def test_deps_get_user_id_no_auth(client):
    """Neither header nor JWT → 401."""
    r = await client.get("/api/nodes")
    assert r.status_code == 401
    body = r.json()
    assert body.get("error_class") == "security" or body.get("detail", {}).get("error_class") == "security"


@pytest.mark.asyncio
async def test_deps_jwt_error_message_contains_reason(client):
    """The 401 body for an invalid JWT includes the reason."""
    import jwt as _jwt
    from datetime import datetime, timedelta, timezone
    payload = {"sub": "u", "exp": datetime.now(timezone.utc) - timedelta(hours=1)}
    token = _jwt.encode(payload, "secret", algorithm="HS256")
    r = await client.get("/api/nodes", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    body = r.json()
    msg = body.get("error_message", "") or body.get("detail", {}).get("error_message", "")
    assert "expired" in msg.lower() or "invalid" in msg.lower()


@pytest.mark.asyncio
async def test_deps_jwt_happy_path_sub_returned_via_endpoint(client):
    """Sanity: when JWT decodes, the user_id flows through to the endpoint."""
    import jwt as _jwt
    token = _jwt.encode({"sub": "bob"}, "secret", algorithm="HS256")
    r = await client.get("/api/nodes", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["node_types"]  # endpoint ran successfully
