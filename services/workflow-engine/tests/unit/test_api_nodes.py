"""Unit tests for app/api/nodes.py — list + per-type schema."""
import pytest
from app.nodes.registry import NODE_REGISTRY


@pytest.mark.asyncio
async def test_list_node_types(client, auth_headers, db_setup):
    r = await client.get("/api/nodes", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "node_types" in data
    assert len(data["node_types"]) == 14
    types = {nt["type"] for nt in data["node_types"]}
    assert "start" in types
    assert "end" in types
    assert "llm" in types


@pytest.mark.asyncio
async def test_get_node_schema_llm(client, auth_headers, db_setup):
    r = await client.get("/api/nodes/llm/schema", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["type"] == "llm"
    assert "config_schema" in data
    assert "properties" in data["config_schema"]


@pytest.mark.asyncio
async def test_get_node_schema_unknown_404(client, auth_headers, db_setup):
    r = await client.get("/api/nodes/nonexistent_type/schema", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_node_types_unauthenticated(client, db_setup):
    """The list endpoint now requires auth (after fix-canvas-lib-gitignore)."""
    r = await client.get("/api/nodes")
    assert r.status_code == 401
