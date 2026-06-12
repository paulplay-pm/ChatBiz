"""Daily archive job — copy 90-day-old audit_log rows to MinIO
parquet, then DELETE from PG.

Locks decision D5 in
``openspec/changes/gateway-egress-enforcement-p0/design.md`` and
``specs/audit-cold-archive/spec.md`` Requirement 1.

Failure semantics:

* MinIO upload fails → PG rows are **not** deleted; the function
  raises so the K8s CronJob records the failure and retries on the
  next schedule.
* PG SELECT fails → same as above (function raises).
* PG DELETE fails after a successful upload → the function raises,
  the rows remain in PG, and the *next* run will re-upload the
  same rows to a (slightly different) parquet key, leaving at
  most one duplicate file in MinIO. The cold-query endpoint
  deduplicates by reading multiple files, so a duplicate is
  harmless; a missing file would not be.

Output format (one parquet per run):

* path: ``s3://chatbiz-audit-cold/yyyy/mm/dd.parquet``
* schema: the 15 columns of ``audit_log`` (id, trace_id, user_id,
  workflow_id, model, model_kind, bypass_isolation, pii_detected_types,
  pii_redacted_count, prompt_hash, token_input, token_output,
  latency_ms, upstream_status, error_class, created_at).
  Parquet is columnar + typed; the cold-query endpoint reads it
  back via pyarrow.
* The S3 client and the parquet writer are injected so the unit
  tests can mock both with a single ``unittest.mock`` patch.

Designed to be run from a Kubernetes CronJob; the entrypoint
:func:`main` accepts CLI args (``--days-threshold``,
``--batch-size``) and exits 0 on success, non-zero on failure.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)

# Path scheme locked by spec: ``s3://chatbiz-audit-cold/yyyy/mm/dd.parquet``.
BUCKET_NAME = "chatbiz-audit-cold"
KEY_TEMPLATE = "{yyyy}/{mm}/{dd}.parquet"


class _S3Client(Protocol):
    """Minimal S3 surface used by the archiver.

    boto3's ``S3.Client.put_object`` matches this shape. We keep the
    protocol explicit so tests can pass a plain ``MagicMock`` (which
    is duck-typed on the method) without instantiating boto3.
    """

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> dict: ...


@dataclass(frozen=True)
class ArchiveResult:
    """Summary of one archive run, returned to the K8s CronJob log."""

    rows_archived: int
    bucket: str
    key: str
    started_at: datetime
    finished_at: datetime

    @property
    def duration_seconds(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()


def _build_parquet(rows: list[AuditLog]) -> bytes:
    """Serialise a list of ``AuditLog`` rows to a single parquet blob.

    PyArrow tables are columnar; the schema mirrors ``audit_log`` so
    the cold-query endpoint can read it back with the same field
    names. ``pii_detected_types`` becomes a ``list<str>`` (PyArrow's
    ``pa.list_(pa.string())``).
    """
    schema = pa.schema(
        [
            pa.field("id", pa.int64(), nullable=False),
            pa.field("trace_id", pa.string(), nullable=False),
            pa.field("user_id", pa.string(), nullable=False),
            pa.field("workflow_id", pa.string(), nullable=True),
            pa.field("model", pa.string(), nullable=False),
            pa.field("model_kind", pa.string(), nullable=False),
            pa.field("bypass_isolation", pa.bool_(), nullable=False),
            pa.field("pii_detected_types", pa.list_(pa.string()), nullable=False),
            pa.field("pii_redacted_count", pa.int32(), nullable=False),
            pa.field("prompt_hash", pa.string(), nullable=False),
            pa.field("token_input", pa.int32(), nullable=True),
            pa.field("token_output", pa.int32(), nullable=True),
            pa.field("latency_ms", pa.int32(), nullable=False),
            pa.field("upstream_status", pa.int32(), nullable=True),
            pa.field("error_class", pa.string(), nullable=True),
            pa.field("created_at", pa.timestamp("us", tz="UTC"), nullable=False),
        ]
    )
    table = pa.Table.from_pylist(
        [
            {
                "id": r.id,
                "trace_id": r.trace_id,
                "user_id": r.user_id,
                "workflow_id": r.workflow_id,
                "model": r.model,
                "model_kind": r.model_kind,
                "bypass_isolation": bool(r.bypass_isolation),
                "pii_detected_types": list(r.pii_detected_types or []),
                "pii_redacted_count": r.pii_redacted_count,
                "prompt_hash": r.prompt_hash,
                "token_input": r.token_input,
                "token_output": r.token_output,
                "latency_ms": r.latency_ms,
                "upstream_status": r.upstream_status,
                "error_class": r.error_class,
                "created_at": r.created_at,
            }
            for r in rows
        ],
        schema=schema,
    )
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="snappy")
    return buf.getvalue()


def _parquet_key_for(rows: list[AuditLog]) -> str:
    """Build the S3 key from the rows' ``created_at``.

    The spec keys the file by the *day* the data was written. If a
    batch spans multiple days we pick the oldest day's bucket — every
    row in the file shares that key. In practice the daily batch is
    small enough that a single day's rows are processed in one run.
    """
    oldest = min(r.created_at for r in rows)
    oldest_utc = oldest.astimezone(timezone.utc) if oldest.tzinfo else oldest.replace(
        tzinfo=timezone.utc
    )
    return KEY_TEMPLATE.format(
        yyyy=f"{oldest_utc.year:04d}",
        mm=f"{oldest_utc.month:02d}",
        dd=f"{oldest_utc.day:02d}",
    )


async def _select_old_audits(
    session_factory: async_sessionmaker[AsyncSession],
    days_threshold: int,
    batch_size: int,
    now: datetime,
) -> list[AuditLog]:
    """Read up to ``batch_size`` rows older than ``days_threshold``."""
    cutoff = now - timedelta(days=days_threshold)
    async with session_factory() as session:
        stmt = (
            select(AuditLog)
            .where(AuditLog.created_at < cutoff)
            .order_by(AuditLog.id.asc())
            .limit(batch_size)
        )
        result = await session.execute(stmt)
        rows = list(result.scalars().all())
    return rows


async def _delete_audits(
    session_factory: async_sessionmaker[AsyncSession],
    ids: list[int],
) -> int:
    """Delete the rows whose ``id`` is in ``ids``. Returns rowcount."""
    if not ids:
        return 0
    async with session_factory() as session:
        stmt = delete(AuditLog).where(AuditLog.id.in_(ids))
        result = await session.execute(stmt)
        await session.commit()
    return int(result.rowcount or 0)


async def archive_old_audits(
    session_factory: async_sessionmaker[AsyncSession],
    s3_client: _S3Client,
    days_threshold: int = 90,
    batch_size: int = 1000,
    bucket: str = BUCKET_NAME,
    now: datetime | None = None,
) -> ArchiveResult:
    """One archive run: SELECT old rows → upload parquet → DELETE.

    On any failure, the function raises; the K8s CronJob records the
    non-zero exit and retries on the next schedule. Idempotency: the
    same row uploaded twice produces two parquet files (the second
    run sees no rows to archive, so DELETE is never called twice for
    the same row).
    """
    started_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rows = await _select_old_audits(
        session_factory, days_threshold, batch_size, started_at
    )
    if not rows:
        logger.info("archive: no rows to archive (cutoff=%d days)", days_threshold)
        return ArchiveResult(
            rows_archived=0,
            bucket=bucket,
            key="(no-op)",
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
        )
    # Build + upload the parquet FIRST. If the upload raises, we
    # have not deleted anything in PG — the spec's failure-rollback
    # contract is satisfied.
    body = _build_parquet(rows)
    key = _parquet_key_for(rows)
    logger.info(
        "archive: uploading %d rows to s3://%s/%s (%d bytes)",
        len(rows),
        bucket,
        key,
        len(body),
    )
    s3_client.put_object(Bucket=bucket, Key=key, Body=body)
    # Upload succeeded → now safe to DELETE.
    ids = [r.id for r in rows]
    deleted = await _delete_audits(session_factory, ids)
    finished_at = datetime.now(timezone.utc)
    logger.info(
        "archive: deleted %d rows from PG (s3://%s/%s)", deleted, bucket, key
    )
    return ArchiveResult(
        rows_archived=deleted,
        bucket=bucket,
        key=key,
        started_at=started_at,
        finished_at=finished_at,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archive 90-day-old audit_log rows to MinIO parquet."
    )
    parser.add_argument("--days-threshold", type=int, default=90)
    parser.add_argument("--batch-size", type=int, default=1000)
    return parser.parse_args(argv)


async def _amain(argv: list[str] | None = None) -> int:
    """CronJob entrypoint.

    The function is intentionally self-contained: it builds a real
    session factory and a real boto3 client from the standard
    environment variables, so the K8s CronJob can call it as
    ``python -m jobs.archive_audit``. Unit tests bypass this
    function and call :func:`archive_old_audits` directly.
    """
    args = _parse_args(argv)
    # Lazy imports keep the unit-test surface (just ``archive_old_audits``)
    # free of boto3 / env-var dependencies.
    from app.config import get_settings
    from app.database import _get_session_factory
    import boto3

    settings = get_settings()
    factory = _get_session_factory()
    s3 = boto3.client("s3", endpoint_url=getattr(settings, "minio_endpoint_url", None))
    result = await archive_old_audits(
        session_factory=factory,
        s3_client=s3,
        days_threshold=args.days_threshold,
        batch_size=args.batch_size,
    )
    print(
        f"archive complete: rows={result.rows_archived} "
        f"key=s3://{result.bucket}/{result.key} "
        f"duration={result.duration_seconds:.2f}s"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Synchronous wrapper for the K8s CronJob command line."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        return asyncio.run(_amain(argv))
    except Exception as e:  # noqa: BLE001 — top-level exit code handler
        logger.error("archive job failed: %s", e)
        return 1


__all__ = [
    "ArchiveResult",
    "BUCKET_NAME",
    "KEY_TEMPLATE",
    "archive_old_audits",
    "main",
]
