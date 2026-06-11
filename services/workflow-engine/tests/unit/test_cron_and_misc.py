"""Unit tests for app/cron/approval_timeout.py + cleanup.py + redis_client.py + middleware generic."""
import pytest
import uuid
from datetime import datetime, timedelta, timezone
from typing import cast

from app.models.workflow import Approval, WorkflowRun


# ---------------------------------------------------------------------------
# Fixture: rebind cron module's SessionLocal to the test engine so cron
# runs see the same in-memory DB the rest of the test uses.
# ---------------------------------------------------------------------------


@pytest.fixture
def cron_db(db_setup, monkeypatch):
    """Patch app.database.SessionLocal to a factory bound to ``db_setup``."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    import app.database as dbmod
    from app.cron import approval_timeout, cleanup

    TestSession = async_sessionmaker(db_setup, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr(dbmod, "SessionLocal", TestSession)
    # cron modules captured the original at import time — patch their ref too
    monkeypatch.setattr(approval_timeout, "SessionLocal", TestSession)
    monkeypatch.setattr(cleanup, "SessionLocal", TestSession)
    return TestSession


# ---------------------------------------------------------------------------
# approval_timeout.check_approval_timeout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approval_timeout_marks_old_pending(cron_db, db_setup):
    """Approvals older than 24h and still pending should flip to timeout."""
    from app.cron.approval_timeout import check_approval_timeout

    TestSession = cron_db
    run_id = uuid.uuid4()
    ap_id = None
    async with TestSession() as s:
        run = WorkflowRun(
            run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1,
            thread_id="t", mode="workflow", status="paused", started_by="u-paul",
        )
        ap = Approval(
            run_id=run_id, node_id="n", approver_user_id="u-paul",
            status="pending",
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),
        )
        s.add_all([run, ap])
        await s.commit()
        ap_id = ap.approval_id

    await check_approval_timeout()

    async with TestSession() as s:
        ap_after = await s.get(Approval, ap_id)
        assert ap_after is not None
        assert ap_after.status == "timeout"
        run_after = await s.get(WorkflowRun, run_id)
        assert run_after is not None
        assert run_after.status == "failed"
        assert run_after.error_class == "user"


@pytest.mark.asyncio
async def test_approval_timeout_skips_recent_pending(cron_db, db_setup):
    """Approvals created < 24h ago should stay pending."""
    from app.cron.approval_timeout import check_approval_timeout

    TestSession = cron_db
    run_id = uuid.uuid4()
    ap_id = None
    async with TestSession() as s:
        run = WorkflowRun(
            run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1,
            thread_id="t", mode="workflow", status="paused", started_by="u-paul",
        )
        ap = Approval(
            run_id=run_id, node_id="n", approver_user_id="u-paul",
            status="pending",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        s.add_all([run, ap])
        await s.commit()
        ap_id = ap.approval_id

    await check_approval_timeout()

    async with TestSession() as s:
        ap_after = await s.get(Approval, ap_id)
        assert ap_after is not None
        assert ap_after.status == "pending"


@pytest.mark.asyncio
async def test_approval_timeout_skips_already_responded(cron_db, db_setup):
    """Approvals that are already approved/rejected should not be touched."""
    from app.cron.approval_timeout import check_approval_timeout

    TestSession = cron_db
    run_id = uuid.uuid4()
    ap_id = None
    async with TestSession() as s:
        run = WorkflowRun(
            run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1,
            thread_id="t", mode="workflow", status="completed", started_by="u-paul",
        )
        ap = Approval(
            run_id=run_id, node_id="n", approver_user_id="u-paul",
            status="approved",
            created_at=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        s.add_all([run, ap])
        await s.commit()
        ap_id = ap.approval_id

    await check_approval_timeout()

    async with TestSession() as s:
        ap_after = await s.get(Approval, ap_id)
        assert ap_after is not None
        assert ap_after.status == "approved"


@pytest.mark.asyncio
async def test_approval_timeout_no_pending_approvals(cron_db, db_setup):
    """No pending approvals: cron should be a no-op without error."""
    from app.cron.approval_timeout import check_approval_timeout
    await check_approval_timeout()  # must not raise


@pytest.mark.asyncio
async def test_approval_timeout_preserves_terminal_run_status(cron_db, db_setup):
    """If the workflow_run is already completed/failed/cancelled, don't change it."""
    from app.cron.approval_timeout import check_approval_timeout

    TestSession = cron_db
    run_id = uuid.uuid4()
    async with TestSession() as s:
        run = WorkflowRun(
            run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1,
            thread_id="t", mode="workflow", status="completed", started_by="u-paul",
        )
        ap = Approval(
            run_id=run_id, node_id="n", approver_user_id="u-paul",
            status="pending",
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),
        )
        s.add_all([run, ap])
        await s.commit()

    await check_approval_timeout()

    async with TestSession() as s:
        run_after = await s.get(WorkflowRun, run_id)
        assert run_after is not None
        assert run_after.status == "completed"


# ---------------------------------------------------------------------------
# cron start/stop wrappers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cron_approval_timeout_start_stop():
    """start_cron() registers a job; stop_cron() shuts down. Run once to cover."""
    from app.cron.approval_timeout import start_cron, stop_cron
    start_cron()
    stop_cron()


@pytest.mark.asyncio
async def test_cron_cleanup_start_stop():
    """start_cron() registers a job; stop_cron() shuts down. Run once to cover."""
    from app.cron.cleanup import start_cron, stop_cron
    start_cron()
    stop_cron()


# ---------------------------------------------------------------------------
# cron.cleanup.cleanup_old_runs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_old_runs_deletes_old_terminal(cron_db, db_setup):
    """Runs older than 90 days in terminal states should be deleted."""
    from app.cron.cleanup import cleanup_old_runs

    TestSession = cron_db
    old_id = uuid.uuid4()
    fresh_id = uuid.uuid4()
    async with TestSession() as s:
        old = WorkflowRun(
            run_id=old_id, workflow_id=uuid.uuid4(), workflow_version=1,
            thread_id="t1", mode="workflow", status="completed", started_by="u",
            ended_at=datetime.now(timezone.utc) - timedelta(days=100),
        )
        fresh = WorkflowRun(
            run_id=fresh_id, workflow_id=uuid.uuid4(), workflow_version=1,
            thread_id="t2", mode="workflow", status="completed", started_by="u",
            ended_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        s.add_all([old, fresh])
        await s.commit()

    await cleanup_old_runs()

    async with TestSession() as s:
        assert await s.get(WorkflowRun, old_id) is None
        assert await s.get(WorkflowRun, fresh_id) is not None


@pytest.mark.asyncio
async def test_cleanup_old_runs_keeps_non_terminal(cron_db, db_setup):
    """Old runs that are not in a terminal state should be preserved."""
    from app.cron.cleanup import cleanup_old_runs

    TestSession = cron_db
    run_id = uuid.uuid4()
    async with TestSession() as s:
        run = WorkflowRun(
            run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1,
            thread_id="t", mode="workflow", status="running", started_by="u",
            ended_at=datetime.now(timezone.utc) - timedelta(days=200),
        )
        s.add(run)
        await s.commit()

    await cleanup_old_runs()

    async with TestSession() as s:
        assert await s.get(WorkflowRun, run_id) is not None


@pytest.mark.asyncio
async def test_cleanup_old_runs_no_op_when_empty(cron_db, db_setup):
    from app.cron.cleanup import cleanup_old_runs
    await cleanup_old_runs()  # must not raise


# ---------------------------------------------------------------------------
# redis_client.dispose_redis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_client_dispose_when_uninitialized():
    """dispose_redis() with no cached instance is a no-op."""
    from app import redis_client as rcm
    rcm._redis = None
    await rcm.dispose_redis()
    assert rcm._redis is None


@pytest.mark.asyncio
async def test_redis_client_get_redis_returns_cached_instance():
    """get_redis() returns a singleton — second call returns same object."""
    from app import redis_client as rcm
    rcm._redis = None
    r1 = rcm.get_redis()
    r2 = rcm.get_redis()
    assert r1 is r2
    await rcm.dispose_redis()


# ---------------------------------------------------------------------------
# errors.middleware.handlers (direct unit tests; the ASGI client doesn't
# reliably route through the exception handler chain for unhandled Exception
# subclasses when wrapped by LifespanManager, so we exercise the handlers
# directly with a synthetic Request/Exception pair).
# ---------------------------------------------------------------------------


class _FakeRequest:
    """Minimal Request shim — only the .headers attribute is read by handlers."""

    def __init__(self, request_id: str | None = None) -> None:
        self.headers = {"X-Request-Id": request_id} if request_id else {}


def _body_str(response) -> str:
    """JSONResponse.body is memoryview; convert to a real str for assertions."""
    raw = bytes(response.body)
    return raw.decode("utf-8")


def _as_request(shim: _FakeRequest):
    """Cast a _FakeRequest shim to a starlette Request for type-checker happiness."""
    from fastapi import Request
    return cast(Request, shim)


@pytest.mark.asyncio
async def test_generic_exception_handler_returns_500():
    """generic_exception_handler() converts a generic Exception to a 500 JSON response."""
    from app.errors.middleware import generic_exception_handler

    response = await generic_exception_handler(_as_request(_FakeRequest()), RuntimeError("kaboom"))
    assert response.status_code == 500
    body = _body_str(response)
    assert '"error_class":"internal"' in body
    assert '"error_message":"internal server error"' in body
    assert "request_id" in body


@pytest.mark.asyncio
async def test_generic_exception_handler_uses_existing_request_id():
    """If X-Request-Id header is set, the handler echoes it back."""
    from app.errors.middleware import generic_exception_handler

    response = await generic_exception_handler(_as_request(_FakeRequest(request_id="req-fixed-id")), RuntimeError("kaboom"))
    body = _body_str(response)
    assert '"request_id":"req-fixed-id"' in body


@pytest.mark.asyncio
async def test_chatbiz_error_handler_status_mapping():
    """user → 422, security → 403, runtime/internal → 502."""
    from app.errors.middleware import chatbiz_error_handler
    from app.errors.classes import UserError, SecurityError, WorkflowRuntimeError, ChatBizError

    req = _as_request(_FakeRequest())

    # user → 422
    r = await chatbiz_error_handler(req, UserError("bad input"))
    assert r.status_code == 422
    assert '"error_class":"user"' in _body_str(r)

    # security → 403
    r = await chatbiz_error_handler(req, SecurityError("denied"))
    assert r.status_code == 403
    assert '"error_class":"security"' in _body_str(r)

    # runtime → 502
    r = await chatbiz_error_handler(req, WorkflowRuntimeError("LLM 5xx"))
    assert r.status_code == 502
    assert '"error_class":"runtime"' in _body_str(r)

    # default (internal) → 502
    r = await chatbiz_error_handler(req, ChatBizError("oops"))
    assert r.status_code == 502
    assert '"error_class":"internal"' in _body_str(r)
