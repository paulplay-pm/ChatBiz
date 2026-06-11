"""Unit tests for app/api/approvals.py — list/resume/cancel."""
import pytest
import uuid
from app.models.workflow import Approval, WorkflowRun


@pytest.mark.asyncio
async def test_list_pending_returns_user_approvals(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    run_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowRun(run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1, thread_id="t", mode="workflow", status="paused", started_by="test-user"))
        s.add(Approval(run_id=run_id, node_id="n1", approver_user_id="test-user", status="pending"))
        await s.commit()
    r = await client.get("/approvals/pending?user=test-user", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert any(a["approver_user_id"] == "test-user" for a in data["approvals"])


@pytest.mark.asyncio
async def test_list_pending_empty(client, auth_headers):
    r = await client.get("/approvals/pending?user=nobody", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.asyncio
async def test_resume_approval_by_approver(client, auth_headers, db_setup):
    """Approver resuming their own pending approval succeeds. We need the actual
    approval_id, so look it up after seeding."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    run_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowRun(run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1, thread_id="t", mode="workflow", status="paused", started_by="test-user"))
        ap = Approval(run_id=run_id, node_id="n1", approver_user_id="test-user", status="pending")
        s.add(ap)
        await s.commit()
        ap_id = ap.approval_id
    r = await client.post(f"/approvals/{ap_id}:resume", headers=auth_headers, json={"decision": "approved", "payload": {}})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_resume_approval_wrong_user_403(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    run_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowRun(run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1, thread_id="t", mode="workflow", status="paused", started_by="u-other"))
        ap = Approval(run_id=run_id, node_id="n1", approver_user_id="u-other", status="pending")
        s.add(ap)
        await s.commit()
        ap_id = ap.approval_id
    r = await client.post(f"/approvals/{ap_id}:resume", headers=auth_headers, json={"decision": "approved", "payload": {}})
    assert r.status_code == 403
    assert r.json().get("error_class") == "security"


@pytest.mark.asyncio
async def test_resume_approval_already_responded_422(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    run_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowRun(run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1, thread_id="t", mode="workflow", status="paused", started_by="test-user"))
        ap = Approval(run_id=run_id, node_id="n1", approver_user_id="test-user", status="approved")
        s.add(ap)
        await s.commit()
        ap_id = ap.approval_id
    r = await client.post(f"/approvals/{ap_id}:resume", headers=auth_headers, json={"decision": "approved", "payload": {}})
    assert r.status_code == 422  # ApprovalAlreadyResponded → user class → 422 (not 409)


@pytest.mark.asyncio
async def test_resume_approval_not_found_422(client, auth_headers):
    r = await client.post(f"/approvals/{uuid.uuid4()}:resume", headers=auth_headers, json={"decision": "approved", "payload": {}})
    assert r.status_code == 422  # ApprovalNotFound → user class → 422


@pytest.mark.asyncio
async def test_cancel_approval_by_starter(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    run_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowRun(run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1, thread_id="t", mode="workflow", status="paused", started_by="test-user"))
        ap = Approval(run_id=run_id, node_id="n1", approver_user_id="u-other", status="pending")
        s.add(ap)
        await s.commit()
        ap_id = ap.approval_id
    r = await client.post(f"/approvals/{ap_id}:cancel", headers=auth_headers, json={})
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    async with TestSession() as s:
        ap2 = await s.get(Approval, ap_id)
        assert ap2 is not None and ap2.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_approval_by_approver(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    run_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowRun(run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1, thread_id="t", mode="workflow", status="paused", started_by="u-other"))
        ap = Approval(run_id=run_id, node_id="n1", approver_user_id="test-user", status="pending")
        s.add(ap)
        await s.commit()
        ap_id = ap.approval_id
    r = await client.post(f"/approvals/{ap_id}:cancel", headers=auth_headers, json={})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_cancel_approval_unauthorized_403(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    run_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowRun(run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1, thread_id="t", mode="workflow", status="paused", started_by="u-other"))
        ap = Approval(run_id=run_id, node_id="n1", approver_user_id="u-other", status="pending")
        s.add(ap)
        await s.commit()
        ap_id = ap.approval_id
    r = await client.post(f"/approvals/{ap_id}:cancel", headers=auth_headers, json={})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_cancel_approval_not_found_422(client, auth_headers):
    r = await client.post(f"/approvals/{uuid.uuid4()}:cancel", headers=auth_headers, json={})
    assert r.status_code == 422  # ApprovalNotFound → user class → 422
