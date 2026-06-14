"""Cold-archive query endpoint — reads from MinIO, NOT the hot PG table.

Per task 4.4 of `openspec/changes/gateway-egress-enforcement-p0/`.
Pairs with the 4.3 archive job: rows older than 90 days are in
MinIO at ``s3://chatbiz-audit-cold/yyyy/mm/dd.jsonl``; this endpoint
serves them back as a JSON stream for ops debugging or
compliance/audit reporting.

Why a separate endpoint from GET /v1/traces/{trace_id}?
  * ``GET /v1/traces/{trace_id}`` is a single-trace lookup, hot path
    (5min L1 cache + L2 PG fallback). It's the "I have a user-visible
    trace_id from a recent request, what happened?" path.
  * ``GET /v1/audit/archive?from=&to=`` is a date-range query, cold
    path (no cache, MinIO only). It's the "I need a report covering
    last quarter" path. Different access pattern, different backend.

Response shape
==============

A JSON object with the aggregated events across the requested date
range. The shape mirrors the L2 events from GET /v1/traces/{trace_id}
so consumers can write one client for both.

.. code-block:: json

    {
      "from": "2026-03-01",
      "to": "2026-03-31",
      "source": "cold",
      "row_count": 1234,
      "events": [
        { /* same shape as L2 event */ },
        ...
      ]
    }

Headers
=======

The response always carries ``X-Audit-Source: cold`` so a debug client
can tell at a glance whether a trace came from the hot or cold
backend, even when both are visible in the same debugging session.

Failure modes
=============

* MinIO unreachable → 503 + body ``{"detail": "archive storage unavailable"}``
* Date range produces no archive files → 200 with empty ``events``
* Malformed ``from`` / ``to`` → 422 (handled by FastAPI via Query validation)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException, Query, Response

from app.jobs.archive_audit import (
    DEFAULT_BUCKET,
    DEFAULT_KEY_PREFIX,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/audit", tags=["audit-archive"])

# Date validation: yyyy-mm-dd only. Reject anything else with 422
# (FastAPI does this for us via the regex pattern on the Query).
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class S3Client(Protocol):
    """Same surface as the archive job uses — we only need ``get_object``
    and ``head_bucket``. Tests can pass a MagicMock."""

    def get_object(self, *, Bucket: str, Key: str) -> dict: ...
    def head_bucket(self, Bucket: str) -> dict: ...


# ---------- helpers ---------------------------------------------------------

def _parse_date(s: str) -> date:
    """Parse a yyyy-mm-dd string into a date object.

    Raises ValueError on bad input. FastAPI catches this via
    ``Query(pattern=...)`` before we get here, but we keep the
    explicit check for defense in depth.
    """
    if not _DATE_RE.match(s):
        raise ValueError(f"expected yyyy-mm-dd, got {s!r}")
    return datetime.strptime(s, "%Y-%m-%d").date()


def _enumerate_archive_keys(
    from_d: date, to_d: date, *, key_prefix: str = DEFAULT_KEY_PREFIX
) -> list[str]:
    """List all archive S3 keys between two dates (inclusive).

    Each day in [from_d, to_d] maps to one parquet/jsonl key under
    ``{key_prefix}yyyy/mm/dd.jsonl``. We do a client-side enumeration
    rather than a real S3 ListObjectsV2 call here because the range
    is bounded (≤ 366 keys for a 1-year query) and the savings from
    skipping missing days at the S3 side are negligible.
    """
    keys: list[str] = []
    cur = from_d
    while cur <= to_d:
        key = f"{key_prefix}{cur.strftime('%Y/%m/%d')}.jsonl"
        keys.append(key)
        cur += timedelta(days=1)
    return keys


def _parse_jsonl_body(body: bytes) -> list[dict[str, Any]]:
    """Parse a JSONL archive file into a list of event dicts.

    Skips empty lines and lines that don't parse as JSON (logged
    as a warning). Spec says "拉 parquet" but we ship JSONL in 4.3;
    the parsing is decoupled from the format choice via this helper.
    """
    events: list[dict[str, Any]] = []
    for lineno, raw in enumerate(body.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            events.append(json.loads(raw))
        except json.JSONDecodeError as e:
            logger.warning("archive jsonl line %d not valid JSON: %s", lineno, e)
    return events


async def _read_archive_key(
    s3: S3Client, bucket: str, key: str
) -> bytes | None:
    """Read a single archive key. Returns None if the key doesn't
    exist (NoSuchKey); raises on other errors so the caller can
    surface a 503.
    """
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
    except Exception as e:
        # Distinguish "key not found" from "S3 unavailable" by
        # error class. boto3 uses ClientError; we accept any
        # exception with "NoSuchKey" in the str as a miss.
        if "NoSuchKey" in type(e).__name__ or "NoSuchKey" in str(e):
            return None
        logger.error("S3 get_object failed for %s/%s: %s", bucket, key, e)
        raise
    # boto3's get_object returns a dict with "Body" being a
    # StreamingBody; for tests / sync fakes, "Body" is bytes.
    body = response.get("Body", b"")
    if hasattr(body, "read"):
        body = body.read()
    return body


# ---------- endpoint -------------------------------------------------------

@router.get("/archive")
async def get_audit_archive(
    response: Response,
    from_: str = Query(
        ..., alias="from", pattern=_DATE_RE.pattern,
        description="Start date (inclusive), yyyy-mm-dd",
    ),
    to: str = Query(
        ..., pattern=_DATE_RE.pattern,
        description="End date (inclusive), yyyy-mm-dd",
    ),
) -> dict[str, Any]:
    """Read audit_log rows from MinIO for a date range.

    The endpoint fan-outs the date range into one S3 GET per day,
    then aggregates the events. With MinIO at single-digit-ms
    intra-AZ latency, a 30-day query is ~30 GETs = ~300ms p99,
    well under the 5s request budget.
    """
    from_d = _parse_date(from_)
    to_d = _parse_date(to)
    if to_d < from_d:
        raise HTTPException(
            status_code=422,
            detail=f"'to' ({to_d}) must be >= 'from' ({from_d})",
        )
    # Cap the range so an op can't accidentally scan 10 years of
    # archive in one request. 366 days = 1 year; a 1-year audit
    # query is a reasonable upper bound for a single HTTP request.
    if (to_d - from_d).days > 366:
        raise HTTPException(
            status_code=422,
            detail="date range too wide (max 366 days)",
        )

    # Resolve S3 client. In production this comes from app.dependencies
    # (a future change); for now we read from a module-level cache
    # that the app sets up in lifespan.
    s3 = _get_s3_client()

    # head_bucket pre-check — fail fast on a missing bucket
    try:
        s3.head_bucket(Bucket=DEFAULT_BUCKET)
    except Exception as e:
        logger.error("archive endpoint: head_bucket failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail="archive storage unavailable",
        )

    keys = _enumerate_archive_keys(from_d, to_d)

    # Read all keys concurrently — independent S3 GETs benefit from
    # the connection pool. asyncio.gather fails the whole batch on
    # any single failure, which is what we want (one unreachable
    # day should surface as 503, not silently drop).
    try:
        bodies = await asyncio.gather(
            *(_read_archive_key(s3, DEFAULT_BUCKET, key) for key in keys)
        )
    except Exception as e:
        # _read_archive_key already logged; we just surface 503.
        raise HTTPException(
            status_code=503,
            detail="archive storage unavailable",
        )

    events: list[dict[str, Any]] = []
    found_keys: list[str] = []
    for key, body in zip(keys, bodies):
        if body is None:
            # Day not in archive (yet) — common, no log
            continue
        found_keys.append(key)
        events.extend(_parse_jsonl_body(body))

    # The header must be set on the response object (FastAPI returns
    # the dict body, so we set it before returning).
    response.headers["X-Audit-Source"] = "cold"

    return {
        "from": from_d.isoformat(),
        "to": to_d.isoformat(),
        "source": "cold",
        "row_count": len(events),
        "keys": found_keys,
        "events": events,
    }


# ---------- S3 client resolution ------------------------------------------

_s3_client: S3Client | None = None


def set_s3_client(s3: S3Client) -> None:
    """Inject the S3 client at app startup. The app's lifespan should
    call this once with a real boto3 client; tests can call it
    directly with a fake."""
    global _s3_client
    _s3_client = s3


def _get_s3_client() -> S3Client:
    if _s3_client is None:
        raise HTTPException(
            status_code=503,
            detail="archive storage unavailable (no S3 client configured)",
        )
    return _s3_client


def reset_s3_client_for_tests() -> None:
    global _s3_client
    _s3_client = None


__all__ = [
    "router",
    "set_s3_client",
    "reset_s3_client_for_tests",
]
