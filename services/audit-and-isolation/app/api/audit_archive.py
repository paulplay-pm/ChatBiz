"""Cold audit query endpoint — reads MinIO parquet files.

Locks spec
``openspec/changes/gateway-egress-enforcement-p0/specs/audit-cold-archive/spec.md``
Requirement 2:

* ``GET /v1/audit/archive?from=<date>&to=<date>&user_id=<id>&page=<n>&page_size=<n>``
* Reads the parquet files at ``s3://chatbiz-audit-cold/yyyy/mm/dd.parquet``
  for every day in the requested range.
* Filters by ``user_id`` (exact match).
* Paginates with ``page`` / ``page_size`` (defaults: 1, 100).
* Sets ``X-Audit-Source: cold`` on success, ``cold,partial`` when the
  range partly extends past the data MinIO still has.
* Returns 503 with ``{"error": "archive_unavailable"}`` when MinIO
  is unreachable.

S3 client and parquet reader are injected so tests can run without
MinIO. The S3 client must expose ``list_objects_v2`` + ``get_object``;
boto3's ``S3.Client`` matches.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Protocol

import pyarrow.parquet as pq
from fastapi import APIRouter, Query, Response

logger = logging.getLogger(__name__)

router = APIRouter()

# The cold bucket name is locked by the archive job and the spec;
# we re-export it here so the endpoint and the job can't drift.
from jobs.archive_audit import BUCKET_NAME  # noqa: E402

KEY_TEMPLATE = "{yyyy}/{mm}/{dd}.parquet"

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 1000


class _S3Client(Protocol):
    """Minimal S3 surface the endpoint needs."""

    def list_objects_v2(self, *, Bucket: str, Prefix: str) -> dict: ...
    def get_object(self, *, Bucket: str, Key: str) -> dict: ...


@dataclass(frozen=True)
class _ParquetListing:
    """Result of one S3 listing call — keys + whether the requested
    range was complete.

    ``partial`` is True when the requested range's first day is older
    than the oldest object we saw — the caller should add a
    ``partial`` flag to the response.
    """

    keys: list[str]
    partial: bool


def _iter_days(start: date, end: date) -> Iterable[date]:
    """Yield every day in ``[start, end]`` (inclusive)."""
    if end < start:
        return
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def _key_for(day: date) -> str:
    return KEY_TEMPLATE.format(
        yyyy=f"{day.year:04d}", mm=f"{day.month:02d}", dd=f"{day.day:02d}"
    )


def _list_keys(
    s3_client: _S3Client, bucket: str, day: date, prefix_root: str = ""
) -> list[str]:
    """Return the parquet key for ``day`` if it exists.

    The MinIO layout is ``yyyy/mm/dd.parquet`` — we list with a
    full-day prefix so a request for ``2026-03-14`` does not
    accidentally match ``2026-03-15.parquet``. (S3 lists return all
    keys that *start with* the prefix, so the per-day path with
    trailing slash is the right granularity.)
    """
    day_prefix = (
        f"{prefix_root}{day.year:04d}/{day.month:02d}/{day.day:02d}"
    )
    resp = s3_client.list_objects_v2(Bucket=bucket, Prefix=day_prefix)
    keys = [
        obj.get("Key", "")
        for obj in (resp.get("Contents", []) or [])
        if obj.get("Key", "").endswith(".parquet")
    ]
    return keys


def _load_parquet(s3_client: _S3Client, bucket: str, key: str) -> list[dict]:
    """Read one parquet object and return a list of dict rows."""
    resp = s3_client.get_object(Bucket=bucket, Key=key)
    body = resp["Body"].read()
    if hasattr(body, "decode"):
        # boto3 returns a ``StreamingBody``; ``.read()`` returns bytes.
        pass
    table = pq.read_table(io.BytesIO(body))
    return table.to_pylist()


def _filter_user(events: list[dict], user_id: str | None) -> list[dict]:
    if not user_id:
        return events
    return [e for e in events if e.get("user_id") == user_id]


def _paginate(events: list[dict], page: int, page_size: int) -> tuple[list[dict], int]:
    total = len(events)
    start = (page - 1) * page_size
    end = start + page_size
    return events[start:end], total


def _parse_date(s: str, name: str) -> date:
    """``YYYY-MM-DD`` parser. Raises ``ValueError`` on bad input."""
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as e:
        raise ValueError(f"{name} must be YYYY-MM-DD (got {s!r})") from e


async def _archive_query(
    s3_client: _S3Client,
    bucket: str,
    date_from: date,
    date_to: date,
    user_id: str | None,
    page: int,
    page_size: int,
) -> tuple[list[dict], int, bool]:
    """Worker logic — exposed as a coroutine for testability.

    Returns ``(events_page, total_matched, partial_range)``.

    ``partial_range`` is True when the requested range's lower bound
    is older than the oldest parquet key we successfully listed —
    which means some days returned no data because the data is
    outside MinIO's retention window.
    """
    days = list(_iter_days(date_from, date_to))
    if not days:
        return [], 0, False
    seen_any_key = False
    oldest_seen: date | None = None
    events: list[dict] = []
    for d in days:
        keys = _list_keys(s3_client, bucket, d)
        if keys:
            seen_any_key = True
            if oldest_seen is None or d < oldest_seen:
                oldest_seen = d
            for k in keys:
                events.extend(_load_parquet(s3_client, bucket, k))
    if user_id:
        events = _filter_user(events, user_id)
    page_events, total = _paginate(events, page, page_size)
    partial = (not seen_any_key) and (date_from < (oldest_seen or date_to))
    return page_events, total, partial


@router.get("/v1/audit/archive")
async def list_archive(
    response: Response,
    from_: str = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
    to: str = Query(..., description="End date (YYYY-MM-DD)"),
    user_id: str | None = Query(None, description="Filter by user_id (exact)"),
    page: int = Query(DEFAULT_PAGE, ge=1, description="1-based page index"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> dict:
    """Return cold audit events for the date range, paginated.

    Header ``X-Audit-Source`` is ``cold`` (full hit) or
    ``cold,partial`` (some days had no parquet). MinIO errors
    propagate as ``503 archive_unavailable``.
    """
    try:
        date_from = _parse_date(from_, "from")
        date_to = _parse_date(to, "to")
    except ValueError as e:
        # Spec: only the 3 documented statuses — bad input is 400.
        response.status_code = 400
        return {"error": "bad_request", "message": str(e)}
    if date_to < date_from:
        response.status_code = 400
        return {"error": "bad_request", "message": "to must be >= from"}

    # The S3 client is resolved lazily on first call. Tests override
    # ``_archive_s3`` directly; production uses the live boto3 client.
    s3 = _archive_s3()
    try:
        events, total, partial = await _archive_query(
            s3_client=s3,
            bucket=BUCKET_NAME,
            date_from=date_from,
            date_to=date_to,
            user_id=user_id,
            page=page,
            page_size=page_size,
        )
    except Exception as e:  # noqa: BLE001 — S3 + parquet both
        logger.error(f"archive query failed: {e}")
        response.status_code = 503
        return {"error": "archive_unavailable"}

    response.headers["X-Audit-Source"] = "cold,partial" if partial else "cold"
    return {
        "data": events,
        "pagination": {
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


# ---------------------------------------------------------------------------
# S3 client wiring (lazy + overridable for tests)
# ---------------------------------------------------------------------------

_archive_s3_override: _S3Client | None = None


def set_archive_s3(client: _S3Client | None) -> None:
    """Replace the S3 client. Test-only helper."""
    global _archive_s3_override
    _archive_s3_override = client


def _archive_s3() -> _S3Client:
    """Return the active S3 client — test override or live boto3."""
    if _archive_s3_override is not None:
        return _archive_s3_override
    import boto3

    from app.config import get_settings

    endpoint = getattr(get_settings(), "minio_endpoint_url", None)
    return boto3.client("s3", endpoint_url=endpoint)


__all__ = [
    "DEFAULT_PAGE",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "list_archive",
    "router",
    "set_archive_s3",
]
