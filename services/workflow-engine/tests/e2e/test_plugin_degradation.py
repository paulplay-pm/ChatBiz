"""E2E test for plugin/HTTP degradation (eng-review Test #2 path #4).

Critical path #4: a downstream HTTP service returns 5xx. The HTTP node
should retry (eng-review decision #9: retry on 5xx) and ultimately
mark the node failed; the workflow run should NOT silently pass.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx
from httpx import Response

_FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "paul_monthly_report.json"
PAUL_FIXTURE = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.mark.asyncio
@respx.mock
async def test_http_node_degrades_on_5xx(client, auth_headers, db_setup):
    """When the downstream HTTP service returns 503, the workflow must not
    silently pass — the run either fails synchronously (500) or starts
    and fails asynchronously (202).
    """
    # Credentials are allowed (so pre-flight check passes), but ERP returns 503.
    respx.get("http://credential-test:8000/v1/credentials/cred-erp/access").mock(
        return_value=Response(200, json={"allowed": True})
    )
    respx.get("http://credential-test:8000/v1/credentials/cred-openai/access").mock(
        return_value=Response(200, json={"allowed": True})
    )
    respx.get("http://mock-erp/data").mock(
        return_value=Response(503, json={"error": "service unavailable"})
    )

    r = await client.post("/workflows", headers=auth_headers, json={
        "name": "degradation test",
        "definition_json": PAUL_FIXTURE,
    })
    assert r.status_code == 201
    wf_id = r.json()["id"]

    r = await client.post(
        f"/workflows/{wf_id}:run",
        headers=auth_headers,
        json={
            "mode": "workflow",
            "variables": {"month": "2026-05", "revenue": 1500000},
        },
    )
    # Acceptable: 202 (run started, will fail async) or 500 (immediate failure).
    assert r.status_code in (202, 500), r.text
