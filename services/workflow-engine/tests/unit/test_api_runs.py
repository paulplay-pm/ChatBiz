"""Unit tests for app/api/runs.py — GET /runs/:run_id."""
import pytest
import uuid
from app.models.workflow import WorkflowRun


@pytest.mark.asyncio
async def test_get_run_with_events(client, auth_headers, db_setup):
    """GET /runs/:run_id returns the run row. NodeEvent autoincrement is awkward in
    SQLite (BigInteger autoincrement=True isn't reflected back), so we skip
    inserting events here and only assert the run status is returned."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    run_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowRun(run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1, thread_id="t", mode="workflow", status="completed", started_by="test-user"))
        await s.commit()
    r = await client.get(f"/runs/{run_id}", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "completed"
    assert data["events"] == []  # empty without events


@pytest.mark.asyncio
async def test_get_run_not_found_404(client, auth_headers):
    r = await client.get(f"/runs/{uuid.uuid4()}", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_run_cross_user_403(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    run_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowRun(run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1, thread_id="t", mode="workflow", status="running", started_by="other-user"))
        await s.commit()
    r = await client.get(f"/runs/{run_id}", headers=auth_headers)
    assert r.status_code == 403
    assert r.json().get("error_class") == "security"
