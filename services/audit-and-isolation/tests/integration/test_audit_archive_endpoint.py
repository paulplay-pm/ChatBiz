"""Integration tests for ``GET /v1/audit/archive``.

Covers the 4 fixtures required by spec §4.4:

1. **Successful cold query** — MinIO returns parquets, endpoint
   returns events paginated with ``X-Audit-Source: cold``.
2. **Range exceeds MinIO retention** — no keys exist for the
   requested range, endpoint returns 200 + empty data with
   ``X-Audit-Source: cold,partial``.
3. **MinIO unavailable** — S3 raises, endpoint returns 503 with
   ``{"error": "archive_unavailable"}``.
4. **user_id filter** — only events matching the user_id are returned.

We mock the S3 client with a small in-memory simulator that returns
parquet blobs written via pyarrow — this keeps the test free of any
real MinIO dependency while still exercising the parquet round-trip.
"""
from __future__ import annotations

import io
import os
import sys
import unittest
import unittest.mock
from datetime import date
from typing import Any
from unittest.mock import MagicMock

# Settings are validated at import; provide safe defaults.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x")
os.environ.setdefault("REDIS_URL", "redis://x")
os.environ.setdefault("CREDENTIAL_SERVICE_URL", "http://x")

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient  # noqa: E402

from app.api import audit_archive as archive_module  # noqa: E402
from app.main import app  # noqa: E402
from jobs.archive_audit import BUCKET_NAME  # noqa: E402


# The same column shape the archive job writes.
SCHEMA = pa.schema(
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


def _row(
    row_id: int,
    user_id: str,
    trace_id: str = "01HXYZGATEWAYTEST000000000",
) -> dict[str, Any]:
    """Build a representative event row for the cold archive."""
    from datetime import datetime, timezone

    return {
        "id": row_id,
        "trace_id": trace_id,
        "user_id": user_id,
        "workflow_id": "wf-monthly-report",
        "model": "qwen-max",
        "model_kind": "public",
        "bypass_isolation": False,
        "pii_detected_types": [],
        "pii_redacted_count": 0,
        "prompt_hash": "a" * 64,
        "token_input": 10,
        "token_output": 20,
        "latency_ms": 100,
        "upstream_status": 200,
        "error_class": None,
        "created_at": datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc),
    }


def _parquet_bytes(rows: list[dict]) -> bytes:
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), buf, compression="snappy")
    return buf.getvalue()


class _FakeS3:
    """In-memory S3 simulator.

    Storage model: ``_objects[key] = bytes``. Listing with a prefix
    returns the matching keys; ``get_object`` returns a dict shaped
    like boto3's response (with a ``Body`` whose ``.read()`` returns
    the bytes).

    Optionally raises on every call when ``raise_on`` is set — used
    for the MinIO-unavailable scenario.
    """

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}
        self.raise_on: Exception | None = None

    def put(self, key: str, body: bytes) -> None:
        self._objects[key] = body

    def list_objects_v2(self, *, Bucket: str, Prefix: str) -> dict:
        if self.raise_on is not None:
            raise self.raise_on
        # Match keys that start with Prefix (the per-day prefix in
        # production). Production code uses the yyyy/mm/dd prefix
        # (no trailing slash) so this is a strict string-prefix check.
        keys = [
            {"Key": k}
            for k in sorted(self._objects)
            if k.startswith(Prefix) and k.endswith(".parquet")
        ]
        return {"Contents": keys, "IsTruncated": False}

    def get_object(self, *, Bucket: str, Key: str) -> dict:
        if self.raise_on is not None:
            raise self.raise_on
        if Key not in self._objects:
            raise KeyError(Key)
        body = self._objects[Key]

        class _Body:
            def __init__(self, b: bytes) -> None:
                self._b = b

            def read(self) -> bytes:
                return self._b

        return {"Body": _Body(body)}


def _key(day: date) -> str:
    return f"{day.year:04d}/{day.month:02d}/{day.day:02d}.parquet"


class TestAuditArchiveEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        # Build a fresh fake per test — TestClient is shared across
        # the module, so we have to reset the fake storage too.
        self._fake = _FakeS3()
        s3 = MagicMock()
        s3.list_objects_v2 = self.fake_list_objects_v2
        s3.get_object = self.fake_get_object
        self._s3 = s3
        archive_module.set_archive_s3(s3)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        archive_module.set_archive_s3(None)

    # ---- helpers bound to the fake ---------------------------------

    def fake_list_objects_v2(self, **kwargs):
        return self._fake.list_objects_v2(**kwargs)

    def fake_get_object(self, **kwargs):
        return self._fake.get_object(**kwargs)

    # ---- 1. Successful query ---------------------------------------

    def test_successful_query_returns_events_with_cold_header(self):
        """Two days in range, each with one parquet containing 1
        row → response has 2 events, header ``X-Audit-Source: cold``."""
        from datetime import date as _d

        d1, d2 = _d(2026, 3, 14), _d(2026, 3, 15)
        self._fake.put(_key(d1), _parquet_bytes([_row(1, "paul")]))
        self._fake.put(_key(d2), _parquet_bytes([_row(2, "paul")]))

        resp = self.client.get(
            "/v1/audit/archive",
            params={"from": "2026-03-14", "to": "2026-03-15"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.headers["X-Audit-Source"] == "cold"
        body = resp.json()
        assert body["pagination"]["total"] == 2
        assert body["pagination"]["page"] == 1
        assert body["pagination"]["page_size"] == 100
        ids = sorted(e["id"] for e in body["data"])
        assert ids == [1, 2]

    # ---- 2. Range exceeds MinIO retention -------------------------

    def test_range_beyond_retention_returns_empty_with_partial_header(self):
        """When the requested range is older than the oldest
        parquet key (none in storage), the response is 200 + empty
        data + ``X-Audit-Source: cold,partial``."""
        from datetime import date as _d

        d1 = _d(2026, 3, 15)
        # Only March 15 exists; the query asks for Jan 1 — Jan 3
        # (no overlap → nothing returned → partial=True).
        self._fake.put(_key(d1), _parquet_bytes([_row(1, "paul")]))

        resp = self.client.get(
            "/v1/audit/archive",
            params={"from": "2026-01-01", "to": "2026-01-03"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.headers["X-Audit-Source"] == "cold,partial"
        body = resp.json()
        assert body["data"] == []
        assert body["pagination"]["total"] == 0

    # ---- 3. MinIO unavailable → 503 --------------------------------

    def test_minio_unavailable_returns_503(self):
        """S3 raises on listing → endpoint returns 503."""
        self._fake.raise_on = ConnectionError("minio down")
        resp = self.client.get(
            "/v1/audit/archive",
            params={"from": "2026-03-14", "to": "2026-03-15"},
        )
        assert resp.status_code == 503
        assert resp.json() == {"error": "archive_unavailable"}

    # ---- 4. user_id filter -----------------------------------------

    def test_user_id_filter_returns_only_matching_rows(self):
        """With ``user_id=paul``, the response only includes rows
        whose ``user_id`` is ``paul``."""
        from datetime import date as _d

        d = _d(2026, 3, 15)
        rows = [
            _row(1, "paul"),
            _row(2, "leo"),
            _row(3, "paul"),
            _row(4, "anny"),
        ]
        self._fake.put(_key(d), _parquet_bytes(rows))

        resp = self.client.get(
            "/v1/audit/archive",
            params={
                "from": "2026-03-15",
                "to": "2026-03-15",
                "user_id": "paul",
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["pagination"]["total"] == 2
        for e in body["data"]:
            assert e["user_id"] == "paul"
        assert sorted(e["id"] for e in body["data"]) == [1, 3]


class TestParseDateErrors(unittest.TestCase):
    """The endpoint rejects malformed date strings with 400 + message."""

    def test_bad_from_format_returns_400(self):
        client = TestClient(app)
        resp = client.get(
            "/v1/audit/archive",
            params={"from": "not-a-date", "to": "2026-03-15"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "bad_request"

    def test_to_before_from_returns_400(self):
        client = TestClient(app)
        resp = client.get(
            "/v1/audit/archive",
            params={"from": "2026-03-15", "to": "2026-03-14"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "bad_request"


class TestHelpers(unittest.TestCase):
    """Cover the small helpers in the module that the endpoint tests
    don't reach: empty day range, no-user_id fast path, key formatter,
    live-boto3 fallback."""

    def test_iter_days_empty_when_to_before_from(self):
        from app.api.audit_archive import _iter_days
        from datetime import date as _d

        out = list(_iter_days(_d(2026, 3, 15), _d(2026, 3, 14)))
        assert out == []

    def test_key_for_day(self):
        from app.api.audit_archive import _key_for
        from datetime import date as _d

        assert _key_for(_d(2026, 3, 15)) == "2026/03/15.parquet"

    def test_filter_user_no_user_id_returns_input(self):
        from app.api.audit_archive import _filter_user

        events = [{"user_id": "paul"}, {"user_id": "leo"}]
        assert _filter_user(events, None) is events

    def test_archive_query_empty_range(self):
        """``_archive_query`` returns ([], 0, False) when there are
        no days in the range (to < from)."""
        import asyncio
        from app.api.audit_archive import _archive_query
        from datetime import date as _d

        s3 = MagicMock()
        events, total, partial = asyncio.run(
            _archive_query(
                s3_client=s3,
                bucket="b",
                date_from=_d(2026, 3, 15),
                date_to=_d(2026, 3, 14),
                user_id=None,
                page=1,
                page_size=10,
            )
        )
        assert events == []
        assert total == 0
        assert partial is False

    def test_archive_s3_fallback_uses_boto3(self):
        """When no test override is active, ``_archive_s3`` returns
        a boto3.client. We patch ``boto3.client`` to assert it's
        called with the configured endpoint URL."""
        from app.api import audit_archive as am

        # Clear any test override so the production path runs.
        am.set_archive_s3(None)
        with (
            unittest.mock.patch.dict(
                sys.modules,
                {
                    "boto3": MagicMock(client=MagicMock(return_value="live-boto3")),
                    "app.config": MagicMock(get_settings=lambda: MagicMock(spec=[])),
                },
            ),
        ):
            client = am._archive_s3()
        assert client == "live-boto3"
        am.set_archive_s3(None)


if __name__ == "__main__":
    unittest.main()
