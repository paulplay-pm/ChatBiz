"""Unit tests for app/api/run.py — POST /workflows/:id:run."""
import pytest
import uuid
import respx
from httpx import Response
from app.models.workflow import WorkflowDefinition


@pytest.mark.asyncio
@respx.mock
async def test_run_workflow_credential_check_403(client, auth_headers, db_setup):
    """If workflow has a credential and user lacks access, return 403."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    defn = {"nodes": [{"id": "n1", "type": "llm", "config": {"credential_id": "cred-1"}}], "edges": []}
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user", definition_json=defn))
        await s.commit()
    respx.get("http://credential-test:8000/v1/credentials/cred-1/access").mock(return_value=Response(403))
    r = await client.post(f"/workflows/{wf_id}:run", headers=auth_headers, json={"mode": "workflow"})
    assert r.status_code == 403
    body = r.json()
    assert body.get("error_class") == "security"


@pytest.mark.asyncio
@respx.mock
async def test_run_workflow_creates_run_row(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    defn = {"nodes": [{"id": "n1", "type": "llm", "config": {"credential_id": "cred-1", "model": "gpt-4", "prompt": "hi"}}], "edges": []}
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user", definition_json=defn))
        await s.commit()
    respx.get("http://credential-test:8000/v1/credentials/cred-1/access").mock(return_value=Response(200, json={"allowed": True}))
    r = await client.post(f"/workflows/{wf_id}:run", headers=auth_headers, json={"mode": "workflow", "variables": {"month": "2026-05"}})
    assert r.status_code == 202
    data = r.json()
    assert "run_id" in data
    assert data["status"] == "pending"
    # Verify workflow_run row created
    from app.models.workflow import WorkflowRun
    from sqlalchemy import select
    async with TestSession() as s:
        result = await s.execute(select(WorkflowRun).where(WorkflowRun.workflow_id == wf_id))
        run = result.scalar_one()
        assert run.status == "pending"
        assert run.started_by == "test-user"
        assert run.mode == "workflow"
        assert run.workflow_version == 1


@pytest.mark.asyncio
async def test_run_workflow_cross_user_403(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="other-user", definition_json={"nodes": [], "edges": []}))
        await s.commit()
    r = await client.post(f"/workflows/{wf_id}:run", headers=auth_headers, json={"mode": "workflow"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_run_workflow_archived_404(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user", definition_json={"nodes": [], "edges": []}, archived=True))
        await s.commit()
    r = await client.post(f"/workflows/{wf_id}:run", headers=auth_headers, json={"mode": "workflow"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_run_workflow_not_found_404(client, auth_headers, db_setup):
    r = await client.post(f"/workflows/{uuid.uuid4()}:run", headers=auth_headers, json={"mode": "workflow"})
    assert r.status_code == 404
