"""E2E test for manual approval flow (eng-review Test #2 path #3).

Critical path #3: an approval node pauses the workflow, the approver
sees the pending row in ``/approvals/pending``, resumes it, and the
workflow continues. Cross-user access must be denied.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
import respx
from httpx import Response
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.workflow import Approval, WorkflowRun
from tests.conftest import make_test_session_factory


@pytest.mark.asyncio
@respx.mock
async def test_approval_pending_listing(client, auth_headers, db_setup):
    """GET /approvals/pending?user=u-paul returns the pending approval row."""
    TestSession = make_test_session_factory(db_setup)

    # Insert a workflow_run + approval row.
    async with TestSession() as s:
        run = WorkflowRun(
            run_id=uuid.uuid4(),
            workflow_id=uuid.uuid4(),
            workflow_version=1,
            thread_id="test-thread",
            mode="workflow",
            status="paused",
            started_by="u-paul",
        )
        s.add(run)
        await s.commit()
        ap = Approval(
            run_id=run.run_id,
            node_id="n_approve",
            approver_user_id="u-paul",
            status="pending",
        )
        s.add(ap)
        await s.commit()

    r = await client.get("/approvals/pending?user=u-paul", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert any(a["approver_user_id"] == "u-paul" for a in body["approvals"])


@pytest.mark.asyncio
async def test_approval_resume_by_approver(client, auth_headers, db_setup):
    """Approval resume by the approver updates status to approved."""
    TestSession = make_test_session_factory(db_setup)

    async with TestSession() as s:
        run = WorkflowRun(
            run_id=uuid.uuid4(),
            workflow_id=uuid.uuid4(),
            workflow_version=1,
            thread_id="test-thread-2",
            mode="workflow",
            status="paused",
            started_by="u-paul",
        )
        s.add(run)
        await s.commit()
        ap = Approval(
            run_id=run.run_id,
            node_id="n_approve",
            approver_user_id="u-paul",
            status="pending",
        )
        s.add(ap)
        await s.commit()
        approval_id = str(ap.approval_id)

    r = await client.post(
        f"/approvals/{approval_id}:resume",
        headers={**auth_headers, "X-User-Id": "u-paul"},
        json={"decision": "approved", "payload": {"comment": "OK"}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_approval_resume_unauthorized(client, auth_headers, db_setup):
    """Approval resume by a non-approver returns 403 with error_class=security."""
    TestSession = make_test_session_factory(db_setup)

    async with TestSession() as s:
        run = WorkflowRun(
            run_id=uuid.uuid4(),
            workflow_id=uuid.uuid4(),
            workflow_version=1,
            thread_id="test-thread-3",
            mode="workflow",
            status="paused",
            started_by="u-paul",
        )
        s.add(run)
        await s.commit()
        ap = Approval(
            run_id=run.run_id,
            node_id="n_approve",
            approver_user_id="u-paul",
            status="pending",
        )
        s.add(ap)
        await s.commit()
        approval_id = str(ap.approval_id)

    # user-b-imposter tries to resume u-paul's approval.
    r = await client.post(
        f"/approvals/{approval_id}:resume",
        headers={**auth_headers, "X-User-Id": "user-b-imposter"},
        json={"decision": "approved", "payload": {}},
    )
    assert r.status_code == 403
    body = r.json()
    assert body["error_class"] == "security"
