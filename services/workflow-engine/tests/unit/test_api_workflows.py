"""Unit tests for app/api/workflows.py — POST/GET list/GET id/GET versions/GET version/PUT/DELETE."""
import pytest
import uuid
from app.models.workflow import WorkflowDefinition, WorkflowRun


@pytest.mark.asyncio
async def test_create_workflow(client, auth_headers, db_setup):
    """POST /workflows returns 201 with the new workflow."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    body = {"name": "test", "definition_json": {"nodes": [{"id": "n1", "type": "start", "config": {}}], "edges": []}}
    r = await client.post("/workflows", headers=auth_headers, json=body)
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["version"] == 1
    assert data["name"] == "test"


@pytest.mark.asyncio
async def test_get_workflow_latest(client, auth_headers, db_setup):
    """GET /workflows/:id returns the latest version."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user",
                                definition_json={"nodes": [], "edges": []}))
        await s.commit()
    r = await client.get(f"/workflows/{wf_id}", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == 1
    assert data["name"] == "t"


@pytest.mark.asyncio
async def test_get_workflow_not_found(client, auth_headers, db_setup):
    r = await client.get(f"/workflows/{uuid.uuid4()}", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_workflow_archived_returns_404(client, auth_headers, db_setup):
    """Archived workflows return 404 (current API)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user",
                                definition_json={"nodes": [], "edges": []}, archived=True))
        await s.commit()
    r = await client.get(f"/workflows/{wf_id}", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_workflow_cross_user_403(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="other-user",
                                definition_json={"nodes": [], "edges": []}))
        await s.commit()
    r = await client.get(f"/workflows/{wf_id}", headers=auth_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_versions(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="v1", created_by="test-user", definition_json={}))
        s.add(WorkflowDefinition(id=wf_id, version=2, name="v2", created_by="test-user", definition_json={}))
        s.add(WorkflowDefinition(id=wf_id, version=3, name="v3", created_by="test-user", definition_json={}))
        await s.commit()
    r = await client.get(f"/workflows/{wf_id}/versions", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data["versions"]) == 3
    assert data["versions"][0]["version"] == 3  # newest first


@pytest.mark.asyncio
async def test_get_specific_version(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="v1", created_by="test-user", definition_json={"a": 1}))
        s.add(WorkflowDefinition(id=wf_id, version=2, name="v2", created_by="test-user", definition_json={"a": 2}))
        await s.commit()
    r = await client.get(f"/workflows/{wf_id}/versions/1", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == 1
    assert data["definition_json"] == {"a": 1}


@pytest.mark.asyncio
async def test_get_specific_version_not_found(client, auth_headers, db_setup):
    r = await client.get(f"/workflows/{uuid.uuid4()}/versions/99", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_workflow_creates_new_version(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="v1", created_by="test-user", definition_json={"old": True}))
        await s.commit()
    r = await client.put(f"/workflows/{wf_id}", headers=auth_headers,
                          json={"definition_json": {"new": True}})
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == 2
    # Verify old version still exists
    r2 = await client.get(f"/workflows/{wf_id}/versions/1", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["definition_json"] == {"old": True}


@pytest.mark.asyncio
async def test_update_archived_workflow_422(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user", definition_json={}, archived=True))
        await s.commit()
    r = await client.put(f"/workflows/{wf_id}", headers=auth_headers, json={"definition_json": {}})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_update_cross_user_403(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="other-user", definition_json={}))
        await s.commit()
    r = await client.put(f"/workflows/{wf_id}", headers=auth_headers, json={"definition_json": {}})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_delete_workflow_soft_deletes(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user", definition_json={}))
        await s.commit()
    r = await client.delete(f"/workflows/{wf_id}", headers=auth_headers)
    assert r.status_code == 204
    # Verify archived
    async with TestSession() as s:
        wf = await s.get(WorkflowDefinition, (wf_id, 1))
        assert wf.archived is True


@pytest.mark.asyncio
async def test_delete_cross_user_403(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="other-user", definition_json={}))
        await s.commit()
    r = await client.delete(f"/workflows/{wf_id}", headers=auth_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_workflow_missing_name_422(client, auth_headers, db_setup):
    r = await client.post("/workflows", headers=auth_headers, json={"definition_json": {}})
    assert r.status_code == 422
