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
async def test_list_workflows_returns_latest_visible_definitions(client, auth_headers, db_setup):
    """GET /workflows returns current user's non-archived latest definitions for Canvas list page."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    archived_id = uuid.uuid4()
    other_id = uuid.uuid4()
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="old", created_by="test-user", definition_json={"mode": "workflow"}))
        s.add(WorkflowDefinition(id=wf_id, version=2, name="latest", created_by="test-user", definition_json={"mode": "workflow"}))
        s.add(WorkflowDefinition(id=archived_id, version=1, name="archived", created_by="test-user", definition_json={}, archived=True))
        s.add(WorkflowDefinition(id=other_id, version=1, name="other", created_by="other-user", definition_json={}))
        await s.commit()

    r = await client.get("/workflows", headers=auth_headers)

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["workflows"] == [
        {
            "id": str(wf_id),
            "version": 2,
            "name": "latest",
            "created_by": "test-user",
            "created_at": data["workflows"][0]["created_at"],
            "archived": False,
            "definition_json": {"mode": "workflow"},
        }
    ]


@pytest.mark.asyncio
async def test_list_workflows_search_filters_by_name(client, auth_headers, db_setup):
    """GET /workflows?search=foo filters by name substring."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=uuid.uuid4(), version=1, name="alpha-monthly", created_by="test-user", definition_json={"mode": "workflow"}))
        s.add(WorkflowDefinition(id=uuid.uuid4(), version=1, name="beta", created_by="test-user", definition_json={"mode": "workflow"}))
        await s.commit()
    r = await client.get("/workflows?search=alpha", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["workflows"][0]["name"] == "alpha-monthly"


@pytest.mark.asyncio
async def test_list_workflows_type_filter(client, auth_headers, db_setup):
    """GET /workflows?type=chatflow filters by definition.mode."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=uuid.uuid4(), version=1, name="wf", created_by="test-user", definition_json={"mode": "workflow"}))
        s.add(WorkflowDefinition(id=uuid.uuid4(), version=1, name="cf", created_by="test-user", definition_json={"mode": "chatflow"}))
        await s.commit()
    r = await client.get("/workflows?type=chatflow", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["workflows"][0]["name"] == "cf"


@pytest.mark.asyncio
async def test_list_workflows_sharing_filter(client, auth_headers, db_setup):
    """GET /workflows?sharing=team filters by definition.sharing."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=uuid.uuid4(), version=1, name="p", created_by="test-user", definition_json={"sharing": "private"}))
        s.add(WorkflowDefinition(id=uuid.uuid4(), version=1, name="t", created_by="test-user", definition_json={"sharing": "team"}))
        await s.commit()
    r = await client.get("/workflows?sharing=team", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["workflows"][0]["name"] == "t"


@pytest.mark.asyncio
async def test_list_workflows_pagination(client, auth_headers, db_setup):
    """GET /workflows?page=2&page_size=1 returns the second page."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    base = uuid.uuid4()
    async with TestSession() as s:
        for i in range(3):
            s.add(WorkflowDefinition(id=uuid.uuid4(), version=1, name=f"w{i}", created_by="test-user", definition_json={"mode": "workflow"}))
        await s.commit()
    r1 = await client.get("/workflows?page=1&page_size=2", headers=auth_headers)
    r2 = await client.get("/workflows?page=2&page_size=2", headers=auth_headers)
    assert r1.status_code == 200
    assert r2.status_code == 200
    d1 = r1.json()
    d2 = r2.json()
    assert d1["total"] == 3
    assert len(d1["workflows"]) == 2
    assert len(d2["workflows"]) == 1
    # pages are disjoint
    ids1 = {w["id"] for w in d1["workflows"]}
    ids2 = {w["id"] for w in d2["workflows"]}
    assert ids1.isdisjoint(ids2)


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
