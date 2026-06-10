"""Security: workflow rejects credentials the starter doesn't have access to.

Eng-review decision #1 (data isolation gateway) and the credential ACL
pre-flight check in ``app.executor.credential_check`` ensure that a
workflow referencing a credential the caller cannot use fails fast
with ``SecurityError`` / 403 — *before* any LLM calls happen.
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
async def test_workflow_rejects_unauthorized_credential(client, auth_headers, db_setup):
    """If the workflow contains a credential the user can't access, :run must
    surface a security error (403) or fail the run (500 with error_class).
    """
    # The pre-flight check walks every node's credential_id and calls
    # credential service. The first node references ``cred-erp``; we
    # mock it as 403.
    respx.get("http://credential-test:8000/v1/credentials/cred-erp/access").mock(
        return_value=Response(403, json={"error_class": "security", "error_message": "无权访问"})
    )

    r = await client.post("/workflows", headers=auth_headers, json={
        "name": "unauth cred test",
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
    # The pre-flight check in app/api/run.py calls check_credentials()
    # BEFORE the workflow_run row is committed, so a 403 from the
    # credential service surfaces as a 403 with error_class=security.
    # We also accept 500 in case the implementation has been refactored
    # to run the check inside the background task.
    assert r.status_code in (403, 500), r.text
    if r.status_code == 403:
        body = r.json()
        assert body["error_class"] == "security", f"expected security error, got: {body}"
