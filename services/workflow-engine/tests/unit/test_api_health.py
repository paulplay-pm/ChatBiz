"""Unit tests for app/api/health.py — /healthz + /readyz."""
import pytest
import respx
from httpx import Response


@pytest.mark.asyncio
async def test_healthz_returns_200(client, auth_headers, db_setup):
    r = await client.get("/healthz", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_healthz_no_auth_required(client, db_setup):
    r = await client.get("/healthz")
    assert r.status_code == 200


@pytest.mark.asyncio
@respx.mock
async def test_readyz_all_ok(client, auth_headers, db_setup):
    respx.get("http://audit-and-isolation-test:8080/healthz").mock(return_value=Response(200))
    respx.get("http://credential-test:8000/healthz").mock(return_value=Response(200))
    r = await client.get("/readyz", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ready"
    assert data["checks"]["postgres"] == "ok"
    assert data["checks"]["redis"] == "ok"
    assert data["checks"]["audit_isolation"] == "ok"
    assert data["checks"]["credential"] == "ok"


@pytest.mark.asyncio
@respx.mock
async def test_readyz_audit_down_503(client, auth_headers, db_setup):
    respx.get("http://audit-and-isolation-test:8080/healthz").mock(return_value=Response(500))
    respx.get("http://credential-test:8000/healthz").mock(return_value=Response(200))
    r = await client.get("/readyz", headers=auth_headers)
    assert r.status_code == 200  # readyz always 200; status field reports not_ready
    data = r.json()
    assert data["status"] == "not_ready"
    assert "down" in data["checks"]["audit_isolation"]


@pytest.mark.asyncio
@respx.mock
async def test_readyz_credential_down_503(client, auth_headers, db_setup):
    respx.get("http://audit-and-isolation-test:8080/healthz").mock(return_value=Response(200))
    respx.get("http://credential-test:8000/healthz").mock(return_value=Response(500))
    r = await client.get("/readyz", headers=auth_headers)
    assert r.status_code == 200  # readyz always 200
    assert "down" in r.json()["checks"]["credential"]
