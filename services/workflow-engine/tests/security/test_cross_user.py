"""Security: cross-user access is denied for workflow resources.

Eng-review decision: workflow ownership is determined by
``created_by`` (string) — not by the workspace / tenant hierarchy yet
(MVP). Tests verify that:

1. user_b cannot read user_a's workflow_definition row
2. user_b cannot update user_a's workflow_definition row
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
async def test_get_workflow_as_other_user_returns_403(client, auth_headers, db_setup):
    """user_a creates a workflow, user_b tries to read it -> 403 security error."""
    # user_a creates
    r = await client.post(
        "/workflows",
        headers={**auth_headers, "X-User-Id": "user-a"},
        json={"name": "user-a workflow", "definition_json": PAUL_FIXTURE},
    )
    assert r.status_code == 201
    wf_id = r.json()["id"]

    # user_b tries to read
    r = await client.get(
        f"/workflows/{wf_id}",
        headers={**auth_headers, "X-User-Id": "user-b"},
    )
    assert r.status_code == 403
    body = r.json()
    assert body["error_class"] == "security", f"expected security error, got: {body}"


@pytest.mark.asyncio
async def test_update_workflow_as_other_user_returns_403(client, auth_headers, db_setup):
    """user_b cannot update user_a's workflow_definition row."""
    r = await client.post(
        "/workflows",
        headers={**auth_headers, "X-User-Id": "user-a"},
        json={"name": "user-a workflow 2", "definition_json": PAUL_FIXTURE},
    )
    assert r.status_code == 201
    wf_id = r.json()["id"]

    r = await client.put(
        f"/workflows/{wf_id}",
        headers={**auth_headers, "X-User-Id": "user-b"},
        json={"name": "hijacked", "definition_json": PAUL_FIXTURE},
    )
    assert r.status_code == 403
    body = r.json()
    assert body["error_class"] == "security", f"expected security error, got: {body}"
