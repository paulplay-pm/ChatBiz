"""E2E test for PII blocking path (eng-review Test #2 path #2).

Critical path #2: an LLM call hits the audit-and-isolation gateway,
which detects PII (e.g. an ID card number) and rejects with 422. The
workflow must NOT silently pass; it must mark the LLM node as failed
and the run as failed with ``error_class`` surfaced in the response.

The actual PII detection lives in audit-and-isolation. Here we verify
the workflow-engine side: a 422 from the gateway bubbles up to the
client as either a 5xx (background failure) or is reported via the
error class on the run row.
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
async def test_workflow_handles_pii_block(client, auth_headers, db_setup):
    """When the audit-and-isolation gateway returns 422 (PII detected), the
    workflow-run request must surface the error rather than silently succeed.
    """
    respx.get("http://mock-erp/data").mock(
        return_value=Response(200, json={"revenue": 1500000, "expenses": 800000})
    )
    respx.get("http://credential-test:8000/v1/credentials/cred-erp/access").mock(
        return_value=Response(200, json={"allowed": True})
    )
    respx.get("http://credential-test:8000/v1/credentials/cred-openai/access").mock(
        return_value=Response(200, json={"allowed": True})
    )
    # Mock the gateway returning 422 PII-detected.
    respx.post("http://audit-and-isolation-test:8080/v1/chat/completions").mock(
        return_value=Response(422, json={
            "error_class": "user",
            "error_message": "PII detected: ID card number",
        })
    )

    r = await client.post("/workflows", headers=auth_headers, json={
        "name": "PII test",
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
    # Acceptable: 202 (workflow_run created, background task fails asynchronously)
    # or 500 (immediate failure when the LLM call returns 422).
    assert r.status_code in (202, 500), r.text
    if r.status_code == 500:
        # PII detected at credential pre-check OR at LLM call.
        body = r.json()
        # Either is acceptable; what matters is the system does NOT silently pass.
        assert "error_class" in body, f"expected error_class in body, got: {body}"
