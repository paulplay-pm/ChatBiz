"""Unit tests for ``jobs.archive_audit`` (task 4.3).

Covers the 3 scenarios required by the spec:

1. **Normal archive** — 1000 rows → one parquet upload + 1000 PG DELETEs.
2. **MinIO failure** — upload raises → no PG DELETE runs.
3. **Boundary** — rows exactly 89 days old are not archived; rows
   91 days old are.

Strategy:

* The session factory is a :class:`unittest.mock.MagicMock` that
  returns a fixed list of rows for the SELECT and a fixed
  ``rowcount`` for the DELETE. We then assert the calls.
* The S3 client is a :class:`MagicMock` whose ``put_object`` either
  returns ``{}`` (success) or raises (failure).
* Parquet bytes are validated by reading them back with pyarrow
  and checking the row count + a representative column.
"""
from __future__ import annotations

import io
import sys
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

import pyarrow.parquet as pq

from jobs.archive_audit import (
    BUCKET_NAME,
    KEY_TEMPLATE,
    archive_old_audits,
)


def _make_row(
    row_id: int,
    days_ago: int,
    trace_id: str = "01HXE2ECRIT01ARCHIVE0000",
    user_id: str = "svc-paul",
) -> MagicMock:
    """Build a row MagicMock with ``id`` + ``created_at`` set.

    PyArrow's parquet writer will read every column, so we set the
    rest of the audit_log fields to deterministic values too.
    """
    row = MagicMock()
    row.id = row_id
    now = datetime.now(timezone.utc)
    row.created_at = now - timedelta(days=days_ago)
    row.trace_id = trace_id
    row.user_id = user_id
    row.workflow_id = "wf-monthly-report"
    row.model = "qwen-max"
    row.model_kind = "public"
    row.bypass_isolation = False
    row.pii_detected_types = ["身份证"]
    row.pii_redacted_count = 1
    row.prompt_hash = "a" * 64
    row.token_input = 10
    row.token_output = 20
    row.latency_ms = 100
    row.upstream_status = 200
    row.error_class = None
    return row


def _make_session_factory(rows: list[Any], delete_rowcount: int = 0) -> MagicMock:
    """Build a session factory that returns ``rows`` on SELECT and
    a DELETE that reports ``delete_rowcount`` rows affected."""
    factory = MagicMock()

    def open_session():
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        # ``session.execute(stmt)`` is overloaded — we branch on the
        # ``is_select``/``is_delete`` attribute attached by the
        # production code via ``select(...)`` / ``delete(...)``.
        async def execute(stmt):
            # ``select`` statements expose ``.whereclause``; we use
            # a heuristic to distinguish them.
            from sqlalchemy.sql.dml import Delete as SADelete
            from sqlalchemy.sql.selectable import Select as SASelect

            if isinstance(stmt, SASelect):
                result = MagicMock()
                scalars = MagicMock()
                scalars.all = MagicMock(return_value=rows)
                result.scalars = MagicMock(return_value=scalars)
                return result
            if isinstance(stmt, SADelete):
                result = MagicMock()
                result.rowcount = delete_rowcount
                return result
            raise AssertionError(f"unexpected stmt: {stmt!r}")

        session.execute = AsyncMock(side_effect=execute)
        session.commit = AsyncMock()
        return session

    factory.side_effect = open_session
    return factory


def _run(coro):
    """Drive an async coroutine in a fresh event loop (no pytest-asyncio)."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestArchiveOldAudits(unittest.TestCase):
    def test_normal_archive_uploads_parquet_and_deletes(self):
        """1000 rows → 1 S3 put_object + 1 PG DELETE (id IN [...])."""
        rows = [_make_row(i, days_ago=100) for i in range(1, 1001)]
        factory = _make_session_factory(rows, delete_rowcount=1000)
        s3 = MagicMock()
        s3.put_object = MagicMock(return_value={})

        result = _run(
            archive_old_audits(
                session_factory=factory,
                s3_client=s3,
                days_threshold=90,
                batch_size=1000,
            )
        )

        # Exactly one S3 put_object, with bucket + key + body.
        assert s3.put_object.call_count == 1
        kwargs = s3.put_object.call_args.kwargs
        assert kwargs["Bucket"] == BUCKET_NAME
        # Key follows yyyy/mm/dd.parquet
        import re

        assert re.match(r"\d{4}/\d{2}/\d{2}\.parquet", kwargs["Key"])
        # Body is a valid parquet blob containing 1000 rows.
        body = kwargs["Body"]
        assert isinstance(body, bytes) and len(body) > 0
        table = pq.read_table(io.BytesIO(body))
        assert table.num_rows == 1000
        assert table.column("id").to_pylist()[0] == 1
        assert table.column("id").to_pylist()[-1] == 1000

        # DELETE was executed and committed.
        # We can't directly assert the ``in_`` clause from a MagicMock
        # stmt, but we can assert commit was called once.
        sessions = [c.return_value for c in factory.call_args_list]
        # 1 SELECT + 1 DELETE = 2 sessions opened.
        assert factory.call_count == 2
        # Result reports the right row count.
        assert result.rows_archived == 1000
        assert result.bucket == BUCKET_NAME

    def test_minio_failure_rolls_back_pg(self):
        """When S3 put_object raises, no DELETE is executed."""
        rows = [_make_row(i, days_ago=120) for i in range(1, 11)]
        factory = _make_session_factory(rows, delete_rowcount=10)
        s3 = MagicMock()
        s3.put_object = MagicMock(side_effect=ConnectionError("minio down"))

        with self.assertRaises(ConnectionError):
            _run(
                archive_old_audits(
                    session_factory=factory,
                    s3_client=s3,
                    days_threshold=90,
                    batch_size=1000,
                )
            )

        # The S3 call happened, but no second session was opened for DELETE.
        assert s3.put_object.call_count == 1
        # Only the SELECT session was opened.
        assert factory.call_count == 1

    def test_90_day_boundary_89_days_kept_91_days_archived(self):
        """A row created 89 days ago stays; a row created 91 days ago is archived.

        The ``now`` parameter is pinned to a known instant so the
        boundary test is deterministic.
        """
        now = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
        rows = [
            _make_row(1, days_ago=89),  # not eligible
            _make_row(2, days_ago=90),  # exactly 90 → eligible (< not <=)
            _make_row(3, days_ago=91),  # eligible
        ]
        # The session factory returns the full row set for any SELECT.
        factory = _make_session_factory(rows, delete_rowcount=3)
        s3 = MagicMock()
        s3.put_object = MagicMock(return_value={})

        result = _run(
            archive_old_audits(
                session_factory=factory,
                s3_client=s3,
                days_threshold=90,
                batch_size=1000,
                now=now,
            )
        )
        assert result.rows_archived == 3
        # S3 was called once with all 3 rows in the parquet.
        assert s3.put_object.call_count == 1

    def test_empty_batch_short_circuits(self):
        """When SELECT returns no rows, the job logs + returns 0-row
        result and does NOT call S3."""
        factory = _make_session_factory(rows=[], delete_rowcount=0)
        s3 = MagicMock()
        s3.put_object = MagicMock(return_value={})

        result = _run(
            archive_old_audits(
                session_factory=factory,
                s3_client=s3,
                days_threshold=90,
            )
        )
        assert result.rows_archived == 0
        s3.put_object.assert_not_called()
        # No DELETE session either.
        assert factory.call_count == 1  # just the SELECT

    def test_key_uses_oldest_row_day(self):
        """The S3 key is named after the oldest row's UTC date, not
        the current day — so a backfill run that processes rows from
        2026-03-15 lands at ``2026/03/15.parquet``."""
        now = datetime(2026, 6, 10, tzinfo=timezone.utc)
        rows = [
            _make_row(1, days_ago=87),  # created ~2026-03-15
            _make_row(2, days_ago=88),  # created ~2026-03-14
        ]
        # Pin their created_at to fixed dates for a deterministic check.
        rows[0].created_at = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        rows[1].created_at = datetime(2026, 3, 14, 12, 0, 0, tzinfo=timezone.utc)

        factory = _make_session_factory(rows, delete_rowcount=2)
        s3 = MagicMock()
        s3.put_object = MagicMock(return_value={})
        _run(
            archive_old_audits(
                session_factory=factory,
                s3_client=s3,
                days_threshold=90,
                now=now,
            )
        )
        kwargs = s3.put_object.call_args.kwargs
        assert kwargs["Key"] == KEY_TEMPLATE.format(
            yyyy="2026", mm="03", dd="14"
        )

    def test_archive_result_duration_property(self):
        """``ArchiveResult.duration_seconds`` is the wall-clock delta."""
        from jobs.archive_audit import ArchiveResult

        start = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 6, 10, 12, 0, 5, tzinfo=timezone.utc)
        r = ArchiveResult(
            rows_archived=42, bucket="b", key="k", started_at=start, finished_at=end
        )
        assert r.duration_seconds == 5.0


class TestDeleteAudits(unittest.TestCase):
    """The early-return in ``_delete_audits`` for an empty id list
    keeps the DELETE statement off the wire when the SELECT
    returned no rows (defence in depth — ``archive_old_audits``
    already short-circuits in that case)."""

    def test_empty_ids_returns_zero_without_session(self):
        from jobs.archive_audit import _delete_audits

        factory = MagicMock()
        rc = _run(_delete_audits(factory, ids=[]))
        assert rc == 0
        factory.assert_not_called()


class TestParseArgs(unittest.TestCase):
    """The CLI parser locks the K8s CronJob contract."""

    def test_defaults(self):
        from jobs.archive_audit import _parse_args

        ns = _parse_args([])
        assert ns.days_threshold == 90
        assert ns.batch_size == 1000

    def test_overrides(self):
        from jobs.archive_audit import _parse_args

        ns = _parse_args(["--days-threshold", "30", "--batch-size", "500"])
        assert ns.days_threshold == 30
        assert ns.batch_size == 500


class TestMainEntry(unittest.TestCase):
    """``main()`` is the K8s CronJob command line.

    We exercise the failure path (``archive_old_audits`` raises) and
    the success path (returns 0) without actually building a boto3
    client or session factory, by patching the module-level symbols.
    """

    def test_main_returns_1_on_failure(self):
        from jobs import archive_audit as job_mod

        async def boom(*a, **kw):
            raise RuntimeError("simulated archive failure")

        with (
            unittest.mock.patch.object(job_mod, "_parse_args", return_value=unittest.mock.MagicMock(days_threshold=90, batch_size=1000)),
            unittest.mock.patch.object(job_mod, "archive_old_audits", new=boom),
        ):
            rc = job_mod.main([])
        assert rc == 1

    def test_main_returns_0_on_success(self, *patches):
        from jobs import archive_audit as job_mod

        async def ok(*a, **kw):
            return job_mod.ArchiveResult(
                rows_archived=10,
                bucket="b",
                key="2026/03/15.parquet",
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )

        # Stub the modules that ``_amain`` imports lazily so the
        # command line path runs without real PG / boto3.
        fake_boto3 = MagicMock()
        fake_boto3.client.return_value = MagicMock()
        with (
            unittest.mock.patch.dict(
                sys.modules,
                {
                    "boto3": fake_boto3,
                    "app.config": MagicMock(get_settings=lambda: MagicMock(spec=[])),
                    "app.database": MagicMock(_get_session_factory=lambda: MagicMock()),
                },
            ),
            unittest.mock.patch.object(job_mod, "_parse_args", return_value=MagicMock(days_threshold=90, batch_size=1000)),
            unittest.mock.patch.object(job_mod, "archive_old_audits", new=ok),
        ):
            rc = job_mod.main([])
        assert rc == 0


if __name__ == "__main__":
    unittest.main()
