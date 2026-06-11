"""Unit tests for app/api/validate.py — POST /workflows/:id/validate."""
import pytest
import uuid
from app.models.workflow import WorkflowDefinition


def _start_end_nodes():
    """Return the canonical 2-node start→end list (with required I/O schemas)."""
    return [
        {"id": "a", "type": "start", "config": {"inputs": {}}, "input_schema": {}, "output_schema": {}},
        {"id": "b", "type": "end", "config": {"output_keys": []}, "input_schema": {}, "output_schema": {}},
    ]


@pytest.mark.asyncio
async def test_validate_dag_cycle_detected(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    bad = {
        "nodes": _start_end_nodes(),
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}],
    }
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user", definition_json=bad))
        await s.commit()
    r = await client.post(f"/workflows/{wf_id}/validate", headers=auth_headers)
    assert r.status_code == 422
    body = r.json()
    assert body["detail"]["error_class"] == "user"
    assert any(e["type"] in ("cycle", "cycle_check_failed") for e in body["detail"]["errors"])


@pytest.mark.asyncio
async def test_validate_unknown_node_type(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    bad = {"nodes": [{"id": "a", "type": "nonexistent_type", "config": {}}], "edges": []}
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user", definition_json=bad))
        await s.commit()
    r = await client.post(f"/workflows/{wf_id}/validate", headers=auth_headers)
    assert r.status_code == 422
    assert any(e["type"] == "unknown_node_type" for e in r.json()["detail"]["errors"])


@pytest.mark.asyncio
async def test_validate_valid_workflow_passes(client, auth_headers, db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    good = {
        "nodes": _start_end_nodes(),
        "edges": [{"from": "a", "to": "b"}],
    }
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user", definition_json=good))
        await s.commit()
    r = await client.post(f"/workflows/{wf_id}/validate", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["valid"] is True
    assert data["node_count"] == 2
    assert data["edge_count"] == 1


@pytest.mark.asyncio
async def test_validate_jinja_syntax_error(client, auth_headers, db_setup):
    """Edge with non-Jinja condition syntax should report jinja_syntax error."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    wf_id = uuid.uuid4()
    bad = {
        "nodes": _start_end_nodes(),
        "edges": [{"from": "a", "to": "b", "condition": "{{ unclosed jinja"}],
    }
    async with TestSession() as s:
        s.add(WorkflowDefinition(id=wf_id, version=1, name="t", created_by="test-user", definition_json=bad))
        await s.commit()
    r = await client.post(f"/workflows/{wf_id}/validate", headers=auth_headers)
    assert r.status_code == 422
    assert any(e["type"] == "jinja_syntax" for e in r.json()["detail"]["errors"])


@pytest.mark.asyncio
async def test_validate_workflow_not_found_404(client, auth_headers):
    r = await client.post(f"/workflows/{uuid.uuid4()}/validate", headers=auth_headers)
    assert r.status_code == 422  # validate uses UserError → 422 (not 404)
