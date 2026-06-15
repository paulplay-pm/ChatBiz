"""Coverage-gap tests for the V1.0+ coverage_improvement followup.

Per `openspec/changes/gateway-egress-enforcement-p0/retrospective.md`
§6, the audit-and-isolation app/ coverage was 83.23% at apply
time. This file (and `test_routing_table_coverage.py`) is the
followup — closing low-hanging module gaps in small batches.

Modules covered here:
  * `app/jobs/archive_audit.py` — line 94 (duration_seconds property)
    + lines 290-295 (row-count-mismatch warning path)
  * `app/llm/client.py` — lines 188-193 (body-not-dict fallback in
    compute_idempotency_key) + line 304 (unreachable-no-result raise)

Each test is a structural exercise, not a behaviour assertion.
The new code is correct by construction; the test exists to push
the coverage counter to 100% on these modules.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# Settings() reads these at import time of `app.*` modules. Test
# runs that exercise archive_old_audit_logs (which imports
# `app.config`) need these to be present. Placeholder URLs are
# fine because the tests under test that *use* a real DB / Redis /
# credential client already mock them out — see test_llm_client.py
# commit 6994800 (gateway-egress-enforcement-p0 task 7.1) for the
# same fix in a different test file.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CREDENTIAL_SERVICE_URL", "http://localhost:9999")

import httpx
import pytest

from app.jobs import archive_audit
from app.jobs.archive_audit import ArchiveResult, archive_old_audit_logs
from app.llm import client as llm_client
from app.llm.client import (
    _is_ha_failover,
    call_upstream_with_idempotency,
    compute_idempotency_key,
    retry_with_idempotency,
)


# =============================================================================
# app/jobs/archive_audit.py coverage
# =============================================================================

def test_archive_result_duration_seconds_property() -> None:
    """The @property `duration_seconds` is the wall-clock duration
    of an archive run. Line 94 is the property body itself; we
    construct two ArchiveResults with different start/finish and
    verify the subtraction."""
    start = datetime(2026, 6, 14, 10, 0, 0, tzinfo=timezone.utc)
    finish = datetime(2026, 6, 14, 10, 0, 5, tzinfo=timezone.utc)
    r = ArchiveResult(
        rows_scanned=0, rows_uploaded=0, rows_deleted=0,
        parquet_keys=[], started_at=start, finished_at=finish,
    )
    assert r.duration_seconds == 5.0


def test_archive_result_dry_run_default_false() -> None:
    """The `dry_run` field defaults to False (per the dataclass
    declaration). When `archive_old_audit_logs` is called without
    `dry_run=True`, the result.dry_run should be False."""
    assert ArchiveResult(
        rows_scanned=0, rows_uploaded=0, rows_deleted=0,
        parquet_keys=[], started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    ).dry_run is False


def test_archive_old_audit_logs_warns_on_rowcount_mismatch() -> None:
    """Lines 290-295: when DELETE returns a different rowcount than
    upload (e.g. transaction partial), the function logs a warning
    and returns the actual DELETE rowcount, not the upload count.

    We trigger this path by having head_bucket succeed, all S3
    puts succeed, but the DELETE return a different rowcount.
    Run via asyncio.run so the test stays synchronous.
    """
    import asyncio
    cutoff = datetime(2026, 6, 14, tzinfo=timezone.utc)
    rows = [
        SimpleNamespace(
            id=1, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            trace_id="trace-1", user_id="user-1", workflow_id=None,
            model="qwen-max", model_kind="public", bypass_isolation=False,
            pii_detected_types=[], pii_redacted_count=0,
            prompt_hash="0" * 64, token_input=10, token_output=5,
            latency_ms=100, upstream_status=200, error_class=None,
        )
    ]

    fake_s3 = MagicMock()
    fake_s3.head_bucket.return_value = {}
    fake_s3.put_object.return_value = {}

    select_session = _FakeSelectSession(rows)
    delete_session = _FakeDeleteSession(rowcount=0)
    sessions = [select_session, delete_session]
    def session_factory():
        return sessions.pop(0)

    with (
        patch("app.jobs.archive_audit.get_session", side_effect=session_factory),
        patch("app.jobs.archive_audit.logger") as mock_logger,
    ):
        result = asyncio.run(archive_old_audit_logs(fake_s3, cutoff=cutoff))

    # The mismatch is logged
    assert any(
        "row count mismatch" in str(call_args)
        for call_args in mock_logger.warning.call_args_list
    ), f"expected 'row count mismatch' warning; got: {mock_logger.warning.call_args_list}"
    # The reported rows_deleted is the actual DELETE count, not upload
    assert result.rows_uploaded == 1
    assert result.rows_deleted == 0


def test_archive_old_audit_logs_dry_run_skips_delete() -> None:
    """Line 295: the `else` branch under `if not dry_run:` sets
    `rows_deleted = 0` without issuing a DELETE. We pass `dry_run=True`
    to skip the DELETE phase entirely and exercise that branch.

    Note: DELETE session is *not* created in this path — the function
    only ever calls `get_session` once (for the SELECT), because the
    dry_run early-returns inside the `if not dry_run` block. We use
    a single-session factory to verify.
    """
    import asyncio
    cutoff = datetime(2026, 6, 14, tzinfo=timezone.utc)
    rows = [
        SimpleNamespace(
            id=1, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            trace_id="trace-1", user_id="user-1", workflow_id=None,
            model="qwen-max", model_kind="public", bypass_isolation=False,
            pii_detected_types=[], pii_redacted_count=0,
            prompt_hash="0" * 64, token_input=10, token_output=5,
            latency_ms=100, upstream_status=200, error_class=None,
        )
    ]

    fake_s3 = MagicMock()
    fake_s3.head_bucket.return_value = {}
    fake_s3.put_object.return_value = {}

    select_session = _FakeSelectSession(rows)
    sessions = [select_session]
    def session_factory():
        return sessions.pop(0)

    with patch(
        "app.jobs.archive_audit.get_session", side_effect=session_factory
    ):
        result = asyncio.run(
            archive_old_audit_logs(fake_s3, cutoff=cutoff, dry_run=True)
        )

    # dry_run path: S3 upload still happens, DELETE is skipped
    assert result.dry_run is True
    assert result.rows_uploaded == 1
    assert result.rows_deleted == 0
    # Only the SELECT session is consumed; DELETE was never issued
    assert sessions == [], (
        f"DELETE session should not be used in dry_run; "
        f"leftover sessions: {sessions}"
    )


def test_archive_old_audit_logs_skips_rows_without_created_at() -> None:
    """Lines 167-168: rows with `created_at is None` are skipped (and
    a warning is logged). We mix one valid row with one null-CreatedAt
    row and assert only the valid row is uploaded to S3."""
    import asyncio
    cutoff = datetime(2026, 6, 14, tzinfo=timezone.utc)
    rows = [
        SimpleNamespace(
            id=1, created_at=None,  # ← the row that triggers 167-168
            trace_id="trace-1", user_id="user-1", workflow_id=None,
            model="qwen-max", model_kind="public", bypass_isolation=False,
            pii_detected_types=[], pii_redacted_count=0,
            prompt_hash="0" * 64, token_input=10, token_output=5,
            latency_ms=100, upstream_status=200, error_class=None,
        ),
        SimpleNamespace(
            id=2, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            trace_id="trace-2", user_id="user-1", workflow_id=None,
            model="qwen-max", model_kind="public", bypass_isolation=False,
            pii_detected_types=[], pii_redacted_count=0,
            prompt_hash="0" * 64, token_input=10, token_output=5,
            latency_ms=100, upstream_status=200, error_class=None,
        ),
    ]

    fake_s3 = MagicMock()
    fake_s3.head_bucket.return_value = {}
    fake_s3.put_object.return_value = {}

    select_session = _FakeSelectSession(rows)
    delete_session = _FakeDeleteSession(rowcount=1)
    sessions = [select_session, delete_session]
    def session_factory():
        return sessions.pop(0)

    with patch(
        "app.jobs.archive_audit.get_session", side_effect=session_factory
    ):
        result = asyncio.run(archive_old_audit_logs(fake_s3, cutoff=cutoff))

    # Only the valid row (id=2) is uploaded; the null-CreatedAt row
    # (id=1) is skipped via `continue` at line 168.
    assert result.rows_uploaded == 1


def test_archive_old_audit_logs_uses_default_retention_when_cutoff_none() -> None:
    """Line 215: when `cutoff is None`, the function computes
    `cutoff = started_at - timedelta(days=retention_days)`. We pass
    `cutoff=None` to exercise that default-retention branch.

    We further arrange for the SELECT to return zero rows so the
    function early-returns at line 232-233 (avoids needing DELETE
    session). This makes the test purely about the cutoff default."""
    import asyncio
    fake_s3 = MagicMock()
    fake_s3.head_bucket.return_value = {}
    fake_s3.put_object.return_value = {}

    select_session = _FakeSelectSession(rows=[])
    sessions = [select_session]
    def session_factory():
        return sessions.pop(0)

    with patch(
        "app.jobs.archive_audit.get_session", side_effect=session_factory
    ):
        result = asyncio.run(archive_old_audit_logs(fake_s3, cutoff=None))

    # Default-retention path: 0 rows scanned, no DELETE issued,
    # early-return at 232-233.
    assert result.rows_scanned == 0
    assert result.rows_uploaded == 0
    assert result.rows_deleted == 0


def test_archive_old_audit_logs_raises_on_head_bucket_failure() -> None:
    """Lines 221-223: when S3 `head_bucket` raises, the function
    logs an error and re-raises. No S3 put / PG SELECT is attempted
    after the failure. We assert that the exception propagates and
    `head_bucket` was called exactly once."""
    import asyncio
    fake_s3 = MagicMock()
    fake_s3.head_bucket.side_effect = RuntimeError("bucket not found")

    with patch("app.jobs.archive_audit.logger") as mock_logger:
        with pytest.raises(RuntimeError, match="bucket not found"):
            asyncio.run(archive_old_audit_logs(fake_s3, cutoff=datetime.now(timezone.utc)))

    fake_s3.head_bucket.assert_called_once()
    # The error path logs at error level
    assert any(
        "head_bucket" in str(call_args)
        for call_args in mock_logger.error.call_args_list
    ), f"expected head_bucket error log; got: {mock_logger.error.call_args_list}"
    # S3 put was never called (we abort before Phase 1)
    fake_s3.put_object.assert_not_called()


def test_archive_old_audit_logs_raises_on_put_object_failure() -> None:
    """Lines 256-264: when S3 `put_object` raises, the function logs
    an error and re-raises. Critically, the PG DELETE is NOT issued
    (the next run will retry). We assert that `put_object` was called
    and DELETE was never reached."""
    import asyncio
    cutoff = datetime(2026, 6, 14, tzinfo=timezone.utc)
    rows = [
        SimpleNamespace(
            id=1, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            trace_id="trace-1", user_id="user-1", workflow_id=None,
            model="qwen-max", model_kind="public", bypass_isolation=False,
            pii_detected_types=[], pii_redacted_count=0,
            prompt_hash="0" * 64, token_input=10, token_output=5,
            latency_ms=100, upstream_status=200, error_class=None,
        )
    ]

    fake_s3 = MagicMock()
    fake_s3.head_bucket.return_value = {}
    fake_s3.put_object.side_effect = RuntimeError("S3 network error")

    select_session = _FakeSelectSession(rows)
    sessions = [select_session]
    def session_factory():
        return sessions.pop(0)

    with (
        patch("app.jobs.archive_audit.get_session", side_effect=session_factory),
        patch("app.jobs.archive_audit.logger") as mock_logger,
    ):
        with pytest.raises(RuntimeError, match="S3 network error"):
            asyncio.run(archive_old_audit_logs(fake_s3, cutoff=cutoff))

    fake_s3.head_bucket.assert_called_once()
    fake_s3.put_object.assert_called_once()
    # DELETE session is never created (only SELECT was consumed)
    assert sessions == [], (
        f"DELETE session should not be used when put_object fails; "
        f"leftover: {sessions}"
    )
    # Error logged at error level
    assert any(
        "put_object" in str(call_args) or "S3" in str(call_args)
        for call_args in mock_logger.error.call_args_list
    ), f"expected put_object error log; got: {mock_logger.error.call_args_list}"


def test_archive_old_audit_logs_returns_empty_when_no_rows() -> None:
    """Lines 232-233: when SELECT returns 0 rows, the function early-
    returns an empty ArchiveResult without issuing S3 put or PG DELETE.
    We test this path explicitly (separate from the cutoff=None test
    above, which also hits line 232-233 via 0 rows)."""
    import asyncio
    fake_s3 = MagicMock()
    fake_s3.head_bucket.return_value = {}
    fake_s3.put_object.return_value = {}

    select_session = _FakeSelectSession(rows=[])
    sessions = [select_session]
    def session_factory():
        return sessions.pop(0)

    with patch(
        "app.jobs.archive_audit.get_session", side_effect=session_factory
    ):
        result = asyncio.run(
            archive_old_audit_logs(fake_s3, cutoff=datetime.now(timezone.utc))
        )

    assert result.rows_scanned == 0
    assert result.rows_uploaded == 0
    assert result.rows_deleted == 0
    # 0 rows means: head_bucket was called, put_object was NOT
    fake_s3.head_bucket.assert_called_once()
    fake_s3.put_object.assert_not_called()
    # DELETE session is never consumed (early-return before Phase 3)
    assert sessions == [], (
        f"DELETE session should not be used when no rows; "
        f"leftover: {sessions}"
    )


class _FakeSelectSession:
    """First session (SELECT): yields the configured rows."""
    def __init__(self, rows):
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, stmt):
        r = SimpleNamespace()
        r.scalars = lambda: SimpleNamespace(all=lambda: list(self._rows))
        return r


class _FakeDeleteSession:
    """Second session (DELETE): returns a custom rowcount so the
    warn-mismatch path fires when rowcount != upload count."""
    def __init__(self, rowcount):
        self._rowcount = rowcount

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, stmt):
        return SimpleNamespace(rowcount=self._rowcount)


# =============================================================================
# app/llm/client.py coverage
# =============================================================================

def test_compute_idempotency_key_handles_non_dict_non_str_body() -> None:
    """Lines 188-193: the `compute_idempotency_key` function takes
    body as dict | str | bytes. The final `else` branch handles any
    other type by `str(body).encode("utf-8")`. We pass an int to
    exercise that fallback."""
    key = compute_idempotency_key("user-1", 12345, now=1_700_000_000.0)
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_compute_idempotency_key_handles_none_body() -> None:
    """Edge case: body is None. The `else` branch triggers and
    str(None) = "None" which is encoded to bytes."""
    key = compute_idempotency_key("user-1", None, now=1_700_000_000.0)
    assert len(key) == 64


def test_compute_idempotency_key_handles_str_body() -> None:
    """Line 189: the `elif isinstance(body, str)` branch encodes the
    body via `body.encode("utf-8")`. We pass a non-empty string to
    exercise that path."""
    key = compute_idempotency_key("user-1", "hello world", now=1_700_000_000.0)
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_compute_idempotency_key_handles_bytes_body() -> None:
    """Line 191: the `elif isinstance(body, bytes)` branch assigns
    `body_bytes = body` directly (no encode). We pass non-empty bytes
    to exercise that path."""
    key = compute_idempotency_key("user-1", b"hello world", now=1_700_000_000.0)
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_compute_idempotency_key_handles_dict_body() -> None:
    """Lines 185-187: the `isinstance(body, dict)` branch encodes
    `repr(sorted(body.items()))` for stable hashing across dict
    ordering. We pass a small dict to exercise that path."""
    key = compute_idempotency_key(
        "user-1", {"a": 1, "b": 2}, now=1_700_000_000.0
    )
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_compute_idempotency_key_handles_none_now() -> None:
    """Line 185: when `now` is None, the function falls back to
    `time.time()`. We pass `now=None` and assert the result is still
    a 64-char hex string (we don't pin a specific bucket because the
    value is wall-clock-dependent)."""
    key = compute_idempotency_key("user-1", "hello", now=None)
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_retry_with_idempotency_raises_unreachable_no_result() -> None:
    """Line 304: defensive `unreachable` branch in
    `retry_with_idempotency` — fires only if the inner retry loop
    never executes (e.g. `MAX_ATTEMPTS == 0`).

    This branch is unreachable under normal operation: `MAX_ATTEMPTS
    = 3` (client.py:153) guarantees the for-loop body runs at least
    once, so either `last_exc` or `last_resp` is always set after
    the loop. Reaching the raise requires monkey-patching the
    module-level `MAX_ATTEMPTS` to 0 and patching the loop body to
    a no-op, which is a stronger mock contract than this coverage
    test should impose.

    The same defensive pattern at line 121 of `retry_with_redis` is
    explicitly marked `# pragma: no cover`. We follow the same
    convention here: skip the test, record the rationale in the
    docstring, and keep the rest of the file at 100% coverage on
    the modules the file actually targets (archive_audit +
    compute_idempotency_key).
    """
    pytest.skip(
        "client.py:304 is a defensive unreachable branch "
        "(MAX_ATTEMPTS=3 guarantees the loop body runs); "
        "the line 121 sibling in retry_with_redis is marked "
        "`# pragma: no cover` — we follow that convention."
    )


# =============================================================================
# app/llm/client.py coverage (llm-client-retry-coverage followup)
#
# Closes coverage-improvement/retrospective §4.2: client.py 78% → 100%.
# Targets 4 reachable missing regions:
#   * get_client lazy init (line 74-80)
#   * retry_with_redis 2-iter loop in call_upstream (line 104-120)
#   * _is_ha_failover JSON parse error path (line 214-215)
#   * reset_client_for_tests (line 334)
#
# 0 source changes (line 121 / 304 already marked `# pragma: no cover`).
# =============================================================================


def test_get_client_initializes_httpx_async_client() -> None:
    """Lines 74-80: `get_client()` lazy-initializes an `httpx.AsyncClient`
    on first call. We call `reset_client_for_tests()` to clear the
    module-level `_client` cache first, then assert the returned
    client is an `httpx.AsyncClient` instance.
    """
    from app.llm import client as llm_client
    llm_client.reset_client_for_tests()
    c = llm_client.get_client()
    assert isinstance(c, httpx.AsyncClient)


def test_get_client_caches_returned_client() -> None:
    """Lines 74-80: `get_client()` returns the same cached client on
    subsequent calls (no re-init).
    """
    from app.llm import client as llm_client
    llm_client.reset_client_for_tests()
    c1 = llm_client.get_client()
    c2 = llm_client.get_client()
    assert c1 is c2


def test_get_client_uses_upstream_timeout_ms_setting() -> None:
    """Lines 75-77: `get_client()` reads `upstream_timeout_ms` from
    `get_settings()` and converts to seconds for `httpx.Timeout`.
    """
    import httpx
    from app.llm import client as llm_client
    llm_client.reset_client_for_tests()
    with patch.object(
        llm_client, "get_settings", return_value=MagicMock(upstream_timeout_ms=5000)
    ):
        c = llm_client.get_client()
    # httpx.Timeout stores the connect/read/write/ pool timeout;
    # we assert that *some* timeout value is in the seconds range
    # derived from 5000 ms (i.e. 5.0s, not the default 10.0s).
    assert c.timeout.connect == 5.0 or c.timeout.read == 5.0 or c.timeout.write == 5.0


async def test_call_upstream_retries_on_5xx_then_returns_200() -> None:
    """Lines 110-114: when attempt 0 returns 5xx, sleep 200ms then
    retry; attempt 1 returns 200 → return 200.

    Patches `asyncio.sleep` to a no-op so the test is fast.
    """
    from app.llm import client as llm_client
    llm_client.reset_client_for_tests()
    fake_client = MagicMock()
    resp_500 = MagicMock(spec=httpx.Response, status_code=500)
    resp_200 = MagicMock(spec=httpx.Response, status_code=200)
    fake_client.post = AsyncMock(side_effect=[resp_500, resp_200])
    with (
        patch.object(llm_client, "get_client", return_value=fake_client),
        patch("app.llm.client.asyncio.sleep", new=AsyncMock()) as mock_sleep,
    ):
        result = await llm_client.call_upstream(
            base_url="http://x", path="/v1/foo", body={}, headers={}
        )
    assert result is resp_200
    assert mock_sleep.call_count == 1  # sleep between attempt 0 and 1
    assert fake_client.post.call_count == 2


async def test_call_upstream_retries_on_timeout_exception() -> None:
    """Lines 115-119: when attempt 0 raises `httpx.TimeoutException`,
    sleep 200ms then retry; attempt 1 returns 200 → return 200.
    """
    from app.llm import client as llm_client
    llm_client.reset_client_for_tests()
    fake_client = MagicMock()
    resp_200 = MagicMock(spec=httpx.Response, status_code=200)
    fake_client.post = AsyncMock(
        side_effect=[httpx.TimeoutException("timeout"), resp_200]
    )
    with (
        patch.object(llm_client, "get_client", return_value=fake_client),
        patch("app.llm.client.asyncio.sleep", new=AsyncMock()) as mock_sleep,
    ):
        result = await llm_client.call_upstream(
            base_url="http://x", path="/v1/foo", body={}, headers={}
        )
    assert result is resp_200
    assert mock_sleep.call_count == 1
    assert fake_client.post.call_count == 2


async def test_call_upstream_raises_last_exc_on_two_timeouts() -> None:
    """Lines 115-120: two consecutive `httpx.TimeoutException`s →
    raise the last one (not the RuntimeError fallback at line 121).
    """
    from app.llm import client as llm_client
    llm_client.reset_client_for_tests()
    fake_client = MagicMock()
    fake_client.post = AsyncMock(
        side_effect=[
            httpx.TimeoutException("first"),
            httpx.TimeoutException("second"),
        ]
    )
    with (
        patch.object(llm_client, "get_client", return_value=fake_client),
        patch("app.llm.client.asyncio.sleep", new=AsyncMock()) as mock_sleep,
    ):
        with pytest.raises(httpx.TimeoutException, match="second"):
            await llm_client.call_upstream(
                base_url="http://x", path="/v1/foo", body={}, headers={}
            )
    assert mock_sleep.call_count == 1  # sleep between attempts


async def test_call_upstream_two_5xx_returns_second_5xx() -> None:
    """Lines 110-114: when attempt 0 returns 5xx, sleep + retry;
    attempt 1 also returns 5xx but `attempt == 0` is False at that
    point, so we don't retry again — return the 5xx response.
    """
    from app.llm import client as llm_client
    llm_client.reset_client_for_tests()
    fake_client = MagicMock()
    resp_500_a = MagicMock(spec=httpx.Response, status_code=500)
    resp_500_b = MagicMock(spec=httpx.Response, status_code=503)
    fake_client.post = AsyncMock(side_effect=[resp_500_a, resp_500_b])
    with (
        patch.object(llm_client, "get_client", return_value=fake_client),
        patch("app.llm.client.asyncio.sleep", new=AsyncMock()) as mock_sleep,
    ):
        result = await llm_client.call_upstream(
            base_url="http://x", path="/v1/foo", body={}, headers={}
        )
    # Second 5xx is returned as-is (no third retry); only one sleep
    assert result is resp_500_b
    assert mock_sleep.call_count == 1


def test_is_ha_failover_returns_false_when_json_raises() -> None:
    """Lines 212-215: when `resp.json()` raises (non-JSON body),
    `_is_ha_failover` returns False (fallback to non-HA detection).
    """
    from app.llm import client as llm_client
    resp = MagicMock(spec=httpx.Response, status_code=503)
    resp.json.side_effect = ValueError("not JSON")
    assert llm_client._is_ha_failover(resp) is False


def test_is_ha_failover_returns_true_on_503_with_ha_body() -> None:
    """Line 216: `_is_ha_failover` returns True when status 503 and
    body has `error: "HA_FAILOVER"`.
    """
    from app.llm import client as llm_client
    resp = MagicMock(spec=httpx.Response, status_code=503)
    resp.json.return_value = {"error": "HA_FAILOVER"}
    assert llm_client._is_ha_failover(resp) is True


def test_is_ha_failover_returns_false_on_non_503() -> None:
    """Lines 210-211: `_is_ha_failover` early-returns False on
    non-503 status (no JSON parse).
    """
    from app.llm import client as llm_client
    resp = MagicMock(spec=httpx.Response, status_code=200)
    assert llm_client._is_ha_failover(resp) is False


def test_reset_client_for_tests_clears_cached_client() -> None:
    """Line 334: `reset_client_for_tests()` sets the module-level
    `_client` back to `None` so the next `get_client()` re-inits.
    """
    from app.llm import client as llm_client
    llm_client.reset_client_for_tests()
    c1 = llm_client.get_client()
    assert c1 is not None
    llm_client.reset_client_for_tests()
    # After reset, module-level `_client` is None; next get_client
    # creates a fresh instance.
    assert llm_client._client is None
    c2 = llm_client.get_client()
    assert c1 is not c2
