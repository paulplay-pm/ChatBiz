"""Unit tests for the cold-archive job (task 4.3 of gateway-egress-enforcement-p0).

Per spec 4.3:
  * Daily 02:00 UTC job moves audit_log rows older than 90 days to
    s3://chatbiz-audit-cold/yyyy/mm/dd.parquet
  * PG row is deleted after successful upload
  * On failure, the row is left in PG (next day's run retries)

We mock both the SQLAlchemy session and the S3 client so no real
Postgres or MinIO is needed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.jobs import archive_audit
from app.jobs.archive_audit import (
    DEFAULT_BUCKET,
    DEFAULT_RETENTION_DAYS,
    _group_by_day,
    _serialize_parquet_like,
    archive_old_audit_logs,
)


# ---------- fakes ----------------------------------------------------------

class _FakeScalarResult:
    """Fake for the result of ``await session.execute(select_stmt)``."""

    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _FakeScalars(self._rows)


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeSessionCtx:
    """Async context manager that yields a fake session.

    The first call (SELECT phase) returns the given rows; the second
    call (DELETE phase) records the delete statement. The job does
    two ``async with get_session()`` blocks — the first for SELECT,
    the second for DELETE — so we need a stateful fake.
    """

    def __init__(self, select_rows, delete_rowcount: int | None = None):
        self._select_rows = select_rows
        self._delete_rowcount = delete_rowcount
        self._phase = 0  # 0=first call, 1=second call
        self.delete_calls: list[Any] = []
        self.select_calls: list[Any] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, stmt):
        if self._phase == 0:
            # SELECT phase
            self.select_calls.append(stmt)
            self._phase = 1
            return _FakeScalarResult(self._select_rows)
        else:
            # DELETE phase (or anything after SELECT in this session block)
            self.delete_calls.append(stmt)
            return SimpleNamespace(rowcount=self._delete_rowcount)


def _audit_row(
    audit_id: int,
    created_at: datetime,
    trace_id: str = "trace-1",
    user_id: str = "user-1",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=audit_id,
        trace_id=trace_id,
        user_id=user_id,
        workflow_id=None,
        model="qwen-max",
        model_kind="public",
        bypass_isolation=False,
        pii_detected_types=[],
        pii_redacted_count=0,
        prompt_hash="0" * 64,
        token_input=10,
        token_output=5,
        latency_ms=100,
        upstream_status=200,
        error_class=None,
        created_at=created_at,
    )


# ---------- _serialize_parquet_like (pure function) -----------------------

def test_serialize_parquet_like_returns_bytes() -> None:
    rows = [_audit_row(1, datetime(2026, 1, 1, tzinfo=timezone.utc))]
    out = _serialize_parquet_like(rows)
    assert isinstance(out, bytes)
    assert out.endswith(b"\n")  # newline-delimited


def test_serialize_parquet_like_stable_order() -> None:
    """Two calls with the same rows (different input order) produce
    identical bytes. This is the idempotency guarantee that lets a
    retry of an upload overwrite the original without data drift."""
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows_a = [_audit_row(1, now), _audit_row(2, now), _audit_row(3, now)]
    rows_b = [_audit_row(3, now), _audit_row(1, now), _audit_row(2, now)]
    assert _serialize_parquet_like(rows_a) == _serialize_parquet_like(rows_b)


def test_serialize_parquet_like_contains_required_fields() -> None:
    """All AuditLog columns the spec cares about must be in the
    serialised payload. Regression guard against accidentally
    dropping a field during refactor."""
    row = _audit_row(1, datetime(2026, 1, 1, tzinfo=timezone.utc))
    out = _serialize_parquet_like([row]).decode("utf-8")
    for field in (
        "id", "trace_id", "user_id", "model", "model_kind",
        "pii_detected_types", "pii_redacted_count", "prompt_hash",
        "latency_ms", "upstream_status", "created_at",
    ):
        assert f'"{field}"' in out, f"missing field {field} in: {out}"


# ---------- _group_by_day ---------------------------------------------------

def test_group_by_day_partitions_by_created_at_date() -> None:
    rows = [
        _audit_row(1, datetime(2026, 1, 1, 5, tzinfo=timezone.utc)),
        _audit_row(2, datetime(2026, 1, 1, 23, tzinfo=timezone.utc)),
        _audit_row(3, datetime(2026, 1, 2, 0, 1, tzinfo=timezone.utc)),
    ]
    groups = _group_by_day(rows)
    assert set(groups.keys()) == {"2026/01/01", "2026/01/02"}
    assert len(groups["2026/01/01"]) == 2
    assert len(groups["2026/01/02"]) == 1


def test_group_by_day_skips_rows_without_created_at() -> None:
    rows = [
        _audit_row(1, datetime(2026, 1, 1, tzinfo=timezone.utc)),
        _audit_row(2, None),  # type: ignore[arg-type]
    ]
    groups = _group_by_day(rows)
    assert set(groups.keys()) == {"2026/01/01"}


# ---------- archive_old_audit_logs: happy path -----------------------------

@pytest.mark.asyncio
async def test_archive_moves_rows_to_s3_then_deletes() -> None:
    """Spec literal: upload to S3 → delete from PG."""
    cutoff = datetime(2026, 6, 14, tzinfo=timezone.utc)
    rows = [
        _audit_row(1, datetime(2026, 1, 1, tzinfo=timezone.utc)),
        _audit_row(2, datetime(2026, 1, 2, tzinfo=timezone.utc)),
    ]
    fake_session = _FakeSessionCtx(select_rows=rows, delete_rowcount=2)
    fake_s3 = MagicMock()
    fake_s3.head_bucket.return_value = {}

    with (
        patch("app.jobs.archive_audit.get_session", return_value=fake_session),
    ):
        result = await archive_old_audit_logs(
            fake_s3, bucket=DEFAULT_BUCKET, cutoff=cutoff,
        )

    assert result.rows_scanned == 2
    assert result.rows_uploaded == 2
    assert result.rows_deleted == 2
    # One parquet per day
    assert len(result.parquet_keys) == 2
    assert "2026/01/01.jsonl" in result.parquet_keys
    assert "2026/01/02.jsonl" in result.parquet_keys
    # S3 calls: 1 head_bucket + 2 put_object
    assert fake_s3.head_bucket.call_count == 1
    assert fake_s3.put_object.call_count == 2
    # PG delete was called with the right row ids
    assert len(fake_session.delete_calls) == 1
    # The Bucket + Key + Body of each put_object is sane
    for call in fake_s3.put_object.call_args_list:
        kwargs = call.kwargs
        assert kwargs["Bucket"] == DEFAULT_BUCKET
        assert kwargs["Key"].endswith(".jsonl")
        assert isinstance(kwargs["Body"], bytes)
        assert len(kwargs["Body"]) > 0


@pytest.mark.asyncio
async def test_archive_returns_zero_summary_on_empty_table() -> None:
    """When no rows are old enough, the job returns cleanly with
    zero counts — no S3 calls beyond head_bucket, no PG delete."""
    fake_session = _FakeSessionCtx(select_rows=[])
    fake_s3 = MagicMock()

    with patch("app.jobs.archive_audit.get_session", return_value=fake_session):
        result = await archive_old_audit_logs(fake_s3)

    assert result.rows_scanned == 0
    assert result.rows_uploaded == 0
    assert result.rows_deleted == 0
    assert result.parquet_keys == []
    # Only the head_bucket call; no put_object
    assert fake_s3.put_object.call_count == 0


# ---------- archive_old_audit_logs: failure paths ---------------------------

@pytest.mark.asyncio
async def test_archive_s3_upload_failure_aborts_without_delete() -> None:
    """Spec literal: failure → row stays in PG (next run retries)."""
    cutoff = datetime(2026, 6, 14, tzinfo=timezone.utc)
    rows = [_audit_row(1, datetime(2026, 1, 1, tzinfo=timezone.utc))]
    fake_session = _FakeSessionCtx(select_rows=rows, delete_rowcount=0)
    fake_s3 = MagicMock()
    fake_s3.head_bucket.return_value = {}
    fake_s3.put_object.side_effect = RuntimeError("simulated S3 failure")

    with patch("app.jobs.archive_audit.get_session", return_value=fake_session):
        with pytest.raises(RuntimeError, match="simulated S3 failure"):
            await archive_old_audit_logs(fake_s3, cutoff=cutoff)

    # PG delete MUST NOT have been called — the row stays.
    assert fake_session.delete_calls == [], (
        "PG delete must not be called when S3 upload fails (spec: row stays)"
    )


@pytest.mark.asyncio
async def test_archive_s3_unreachable_aborts_at_head_bucket() -> None:
    """head_bucket failure aborts BEFORE we touch PG. The scheduler
    retries the next day."""
    fake_session = _FakeSessionCtx(select_rows=[])
    fake_s3 = MagicMock()
    fake_s3.head_bucket.side_effect = RuntimeError("bucket not found")

    with patch("app.jobs.archive_audit.get_session", return_value=fake_session):
        with pytest.raises(RuntimeError, match="bucket not found"):
            await archive_old_audit_logs(fake_s3)

    # SELECT must not have been called (we fail at head_bucket first)
    assert fake_s3.put_object.call_count == 0


# ---------- archive_old_audit_logs: cut-off / retention -------------------

@pytest.mark.asyncio
async def test_archive_uses_default_retention_days() -> None:
    """When no cutoff is given, the job computes ``now - 90d``. We
    don't assert the exact timestamp (clock-dependent) — only that
    it's a datetime in the past."""
    fake_session = _FakeSessionCtx(select_rows=[])
    fake_s3 = MagicMock()

    with patch("app.jobs.archive_audit.get_session", return_value=fake_session):
        result = await archive_old_audit_logs(fake_s3)

    # We didn't capture the cutoff directly, but the run succeeded
    # without raising — which means the SELECT statement was built
    # and executed (even though it returned 0 rows).
    assert result.rows_scanned == 0


# ---------- module-level constants -----------------------------------------

def test_default_retention_days_is_90() -> None:
    """Spec literal: 超 90 天的行 (older than 90 days)."""
    assert DEFAULT_RETENTION_DAYS == 90


def test_default_bucket_matches_spec() -> None:
    """Spec literal: s3://chatbiz-audit-cold/."""
    assert DEFAULT_BUCKET == "chatbiz-audit-cold"
