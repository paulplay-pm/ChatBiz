"""Integration tests for GET /v1/audit/archive (task 4.4).

Per spec 4.4 of `openspec/changes/gateway-egress-enforcement-p0/`. Verifies:

  1. Date-range query returns aggregated events from MinIO
  2. Response always carries `X-Audit-Source: cold` header
  3. MinIO failure → 503

Plus negative paths:
  4. Malformed date (not yyyy-mm-dd) → 422
  5. 'to' < 'from' → 422
  6. Date range > 366 days → 422
  7. No archive data in range → 200 with empty events

Strategy: inject a fake S3 client via set_s3_client() (the same
mechanism the lifespan would use in production). No real MinIO.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import audit_archive as audit_archive_mod


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app, raise_server_exceptions=True)


# ---------- fakes ----------------------------------------------------------

class _S3WithKeys:
    """Fake S3 that returns canned jsonl bodies for known keys,
    raises NoSuchKey for unknown ones, raises ConnectionError on
    head_bucket failure (to test 503)."""

    def __init__(
        self,
        bodies: dict[str, bytes] | None = None,
        *,
        head_bucket_raises: Exception | None = None,
        get_object_raises: Exception | None = None,
    ):
        self._bodies = bodies or {}
        self._head_bucket_raises = head_bucket_raises
        self._get_object_raises = get_object_raises
        self.head_bucket_calls: list[str] = []
        self.get_object_calls: list[tuple[str, str]] = []

    def head_bucket(self, Bucket: str):
        self.head_bucket_calls.append(Bucket)
        if self._head_bucket_raises is not None:
            raise self._head_bucket_raises
        return {}

    def get_object(self, *, Bucket: str, Key: str):
        self.get_object_calls.append((Bucket, Key))
        if self._get_object_raises is not None:
            raise self._get_object_raises
        if Key not in self._bodies:
            # Mimic boto3's NoSuchKey exception
            raise _NoSuchKey(f"key {Key!r} not found")
        return {"Body": self._bodies[Key]}


class _NoSuchKey(Exception):
    """Stand-in for botocore.exceptions.NoSuchKey."""


def _event(id_: int, trace_id: str = "trace-1", day: str = "2026-03-01") -> dict:
    """One archived audit event."""
    return {
        "id": id_,
        "trace_id": trace_id,
        "user_id": "user-1",
        "workflow_id": None,
        "model": "qwen-max",
        "model_kind": "public",
        "bypass_isolation": False,
        "pii_detected_types": [],
        "pii_redacted_count": 0,
        "prompt_hash": "0" * 64,
        "token_input": 10,
        "token_output": 5,
        "latency_ms": 100,
        "upstream_status": 200,
        "error_class": None,
        "created_at": f"{day}T00:00:00+00:00",
    }


def _jsonl(*events: dict) -> bytes:
    return ("\n".join(json.dumps(e) for e in events) + "\n").encode("utf-8")


# ---------- happy path ------------------------------------------------------

def test_archive_query_aggregates_events_from_s3(client: TestClient) -> None:
    """Spec literal: query + response shape + X-Audit-Source header."""
    fake = _S3WithKeys({
        "2026/03/01.jsonl": _jsonl(_event(1), _event(2)),
        "2026/03/02.jsonl": _jsonl(_event(3)),
        "2026/03/03.jsonl": _jsonl(),  # empty day, no events
    })
    audit_archive_mod.set_s3_client(fake)
    try:
        resp = client.get("/v1/audit/archive?from=2026-03-01&to=2026-03-03")
    finally:
        audit_archive_mod.reset_s3_client_for_tests()

    assert resp.status_code == 200
    assert resp.headers.get("X-Audit-Source") == "cold", (
        f"missing/incorrect X-Audit-Source header: {dict(resp.headers)}"
    )
    body = resp.json()
    assert body["from"] == "2026-03-01"
    assert body["to"] == "2026-03-03"
    assert body["source"] == "cold"
    assert body["row_count"] == 3
    assert len(body["events"]) == 3
    assert {e["id"] for e in body["events"]} == {1, 2, 3}
    assert body["keys"] == ["2026/03/01.jsonl", "2026/03/02.jsonl", "2026/03/03.jsonl"]


def test_archive_query_single_day(client: TestClient) -> None:
    fake = _S3WithKeys({
        "2026/03/15.jsonl": _jsonl(_event(1, day="2026-03-15")),
    })
    audit_archive_mod.set_s3_client(fake)
    try:
        resp = client.get("/v1/audit/archive?from=2026-03-15&to=2026-03-15")
    finally:
        audit_archive_mod.reset_s3_client_for_tests()

    assert resp.status_code == 200
    body = resp.json()
    assert body["row_count"] == 1
    assert body["events"][0]["id"] == 1


def test_archive_query_with_no_data_in_range(client: TestClient) -> None:
    """Days not yet archived return 200 with empty events list."""
    fake = _S3WithKeys({})  # every day is NoSuchKey
    audit_archive_mod.set_s3_client(fake)
    try:
        resp = client.get("/v1/audit/archive?from=2026-03-01&to=2026-03-05")
    finally:
        audit_archive_mod.reset_s3_client_for_tests()

    assert resp.status_code == 200
    body = resp.json()
    assert body["row_count"] == 0
    assert body["events"] == []
    assert resp.headers.get("X-Audit-Source") == "cold"


# ---------- 503 on MinIO failure -------------------------------------------

def test_archive_minio_unreachable_returns_503(client: TestClient) -> None:
    """Spec literal: MinIO 失败 503."""
    fake = _S3WithKeys(head_bucket_raises=ConnectionError("simulated S3 down"))
    audit_archive_mod.set_s3_client(fake)
    try:
        resp = client.get("/v1/audit/archive?from=2026-03-01&to=2026-03-01")
    finally:
        audit_archive_mod.reset_s3_client_for_tests()

    assert resp.status_code == 503
    body = resp.json()
    assert "unavailable" in body["detail"].lower()


def test_archive_get_object_failure_returns_503(client: TestClient) -> None:
    """head_bucket succeeds but a per-key get_object fails — still 503."""
    fake = _S3WithKeys(
        bodies={},
        get_object_raises=ConnectionError("simulated network blip"),
    )
    audit_archive_mod.set_s3_client(fake)
    try:
        resp = client.get("/v1/audit/archive?from=2026-03-01&to=2026-03-01")
    finally:
        audit_archive_mod.reset_s3_client_for_tests()

    assert resp.status_code == 503


# ---------- 422 on bad input ----------------------------------------------

def test_archive_malformed_from_date_returns_422(client: TestClient) -> None:
    resp = client.get("/v1/audit/archive?from=2026-3-1&to=2026-03-31")
    assert resp.status_code == 422


def test_archive_to_before_from_returns_422(client: TestClient) -> None:
    resp = client.get("/v1/audit/archive?from=2026-03-31&to=2026-03-01")
    assert resp.status_code == 422
    assert "to" in resp.text.lower()


def test_archive_range_too_wide_returns_422(client: TestClient) -> None:
    """Max range is 366 days (1 year); 400 days is rejected."""
    resp = client.get(
        f"/v1/audit/archive?from={date(2024, 1, 1).isoformat()}"
        f"&to={date(2024, 1, 1) + timedelta(days=400)}"
    )
    assert resp.status_code == 422
    assert "wide" in resp.text.lower() or "range" in resp.text.lower()


def test_archive_range_at_limit_succeeds(client: TestClient) -> None:
    """Exactly 366 days is allowed (boundary)."""
    fake = _S3WithKeys({})
    audit_archive_mod.set_s3_client(fake)
    try:
        resp = client.get(
            f"/v1/audit/archive?from=2025-01-01&to=2026-01-01"  # 366 days
        )
    finally:
        audit_archive_mod.reset_s3_client_for_tests()
    assert resp.status_code == 200


# ---------- 503 when S3 client not configured -----------------------------

def test_archive_no_s3_client_returns_503(client: TestClient) -> None:
    """If lifespan never called set_s3_client, the endpoint 503s
    with a specific message — distinguishable from a real S3 outage
    by the detail text."""
    audit_archive_mod.reset_s3_client_for_tests()
    resp = client.get("/v1/audit/archive?from=2026-03-01&to=2026-03-01")
    assert resp.status_code == 503
    assert "no s3 client" in resp.json()["detail"].lower()
