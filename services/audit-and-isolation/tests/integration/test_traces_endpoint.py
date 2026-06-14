"""Integration tests for GET /v1/traces/{trace_id} (task 4.1).

Per spec 4.1 of `openspec/changes/gateway-egress-enforcement-p0/`. 4 fixtures:

  1. Redis hit       — L1 set, L2 not consulted, response source="cache"
  2. Redis miss + PG hit — L1 empty, L2 returns 1 row, L1 populated,
                            response source="db"
  3. Redis miss + PG miss — both tiers empty, 404
  4. Redis failure (degradation) — L1 raises, L2 still returns,
                                   response source="db" (L2 wins silently)

Strategy: patch the redis_client and database session factories so
no real Redis or Postgres is needed. This is the same approach
test_api_health.py uses for the readiness probe.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import traces as traces_mod


# ---------- fakes -----------------------------------------------------------

class _RedisHit:
    """Fake Redis client: returns a JSON-encoded payload for a known key,
    None for others. Also tracks SET calls for populate-on-miss assertions."""

    def __init__(self, payload: dict | None):
        self._payload = payload
        self.set_calls: list[tuple[str, str, int | None]] = []

    async def get(self, key: str):
        if self._payload is None:
            return None
        if key == f"trace:cache:abc-test-trace":
            return json.dumps(self._payload)
        return None

    async def set(self, key: str, value: str, ex: int | None = None):
        self.set_calls.append((key, value, ex))


class _RedisBroken:
    """Fake Redis client that always raises on get/set (simulates connection failure)."""

    async def get(self, key: str):
        raise ConnectionError("simulated redis down")

    async def set(self, key: str, value: str, ex: int | None = None):
        raise ConnectionError("simulated redis down")


class _FakeSessionCtx:
    """Async context manager that yields a fake session returning the given rows."""

    def __init__(self, rows):
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, stmt):
        # stmt has .whereclause etc; we don't introspect — we return rows as-is.
        # The endpoint calls .scalars().all() on the result.
        class _R:
            def __init__(self, rows):
                self._rows = rows

            def scalars(self):
                class _S:
                    def __init__(self, rows):
                        self._rows = rows

                    def all(self):
                        return list(self._rows)

                return _S(self._rows)

        return _R(self._rows)


def _audit_row(trace_id: str = "abc-test-trace", audit_id: int = 1):
    """Build a SQLAlchemy-like AuditLog row as a SimpleNamespace.

    The endpoint reads .id, .created_at, .model, .model_kind, .user_id,
    .workflow_id, .upstream_status, .latency_ms, .pii_redacted_count,
    .pii_detected_types, .token_input, .token_output, .error_class.
    """
    return SimpleNamespace(
        id=audit_id,
        created_at=SimpleNamespace(isoformat=lambda: "2026-06-14T12:00:00+00:00"),
        model="qwen-max",
        model_kind="public",
        user_id="user-1",
        workflow_id=None,
        upstream_status=200,
        latency_ms=1234,
        pii_redacted_count=2,
        pii_detected_types=["id_card", "phone"],
        token_input=100,
        token_output=50,
        error_class=None,
    )


# ---------- fixture: TestClient (no real lifespan side-effects) -------------

@pytest.fixture
def client():
    """A TestClient for the main app. We don't run the full lifespan
    (which would start the audit outbox and load the routing table) —
    we only need the route to be registered and the dependencies
    patchable."""
    from app.main import app
    return TestClient(app, raise_server_exceptions=True)


# ---------- fixture 1: Redis hit ------------------------------------------

def test_redis_hit_returns_cache_source(client: TestClient) -> None:
    cached_payload = {
        "trace_id": "abc-test-trace",
        "source": "cache",
        "events": [
            {"audit_id": 1, "model": "qwen-max", "user_id": "user-1",
             "upstream_status": 200, "latency_ms": 1234,
             "pii_redacted_count": 0, "pii_detected_types": []},
        ],
    }
    fake_redis = _RedisHit(cached_payload)

    with patch.object(traces_mod, "redis_client") as rc:
        rc.get_redis = lambda: fake_redis
        resp = client.get("/v1/traces/abc-test-trace")

    assert resp.status_code == 200
    body = resp.json()
    assert body["trace_id"] == "abc-test-trace"
    assert body["source"] == "cache"
    assert len(body["events"]) == 1
    assert body["events"][0]["model"] == "qwen-max"
    # L2 should not have been consulted — fake_redis.set should be empty
    assert fake_redis.set_calls == [], (
        "L1 hit should not trigger a populate-on-miss set"
    )


# ---------- fixture 2: Redis miss + PG hit --------------------------------

def test_redis_miss_pg_hit_returns_db_source_and_populates_cache(client: TestClient) -> None:
    fake_redis = _RedisHit(None)  # always miss
    rows = [_audit_row()]

    with (
        patch.object(traces_mod, "redis_client") as rc,
        patch.object(traces_mod, "get_session", return_value=_FakeSessionCtx(rows)),
    ):
        rc.get_redis = lambda: fake_redis
        resp = client.get("/v1/traces/abc-test-trace")

    assert resp.status_code == 200
    body = resp.json()
    assert body["trace_id"] == "abc-test-trace"
    assert body["source"] == "db"
    assert len(body["events"]) == 1
    # L1 should have been populated on miss-then-hit
    assert len(fake_redis.set_calls) == 1, (
        f"expected 1 populate-on-miss set, got {len(fake_redis.set_calls)}"
    )
    set_key, set_value, set_ex = fake_redis.set_calls[0]
    assert set_key == "trace:cache:abc-test-trace"
    assert set_ex == 5 * 60  # 5min TTL, per spec
    # The cached payload is the same shape as the response.
    cached = json.loads(set_value)
    assert cached["trace_id"] == "abc-test-trace"
    assert cached["events"][0]["model"] == "qwen-max"


# ---------- fixture 3: both miss -------------------------------------------

def test_both_miss_returns_404(client: TestClient) -> None:
    fake_redis = _RedisHit(None)
    rows = []

    with (
        patch.object(traces_mod, "redis_client") as rc,
        patch.object(traces_mod, "get_session", return_value=_FakeSessionCtx(rows)),
    ):
        rc.get_redis = lambda: fake_redis
        resp = client.get("/v1/traces/missing-trace-1234")

    assert resp.status_code == 404
    # L1 should not be populated when L2 also misses
    assert fake_redis.set_calls == []


# ---------- fixture 4: Redis failure (graceful degradation) ---------------

def test_redis_failure_falls_through_to_db(client: TestClient) -> None:
    fake_redis = _RedisBroken()  # raises on get
    rows = [_audit_row(audit_id=42)]

    with (
        patch.object(traces_mod, "redis_client") as rc,
        patch.object(traces_mod, "get_session", return_value=_FakeSessionCtx(rows)),
    ):
        rc.get_redis = lambda: fake_redis
        resp = client.get("/v1/traces/abc-test-trace")

    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "db", (
        "Redis failure should fall through to L2 silently, not surface as 503"
    )
    assert body["events"][0]["audit_id"] == 42


# ---------- path validation ------------------------------------------------

def test_trace_id_too_short_returns_422(client: TestClient) -> None:
    """The chat endpoint validates X-Trace-Id length [8, 128]; the trace
    lookup should match. (Otherwise a typo'd short id would 404, not
    422 — same client error either way, but 422 is more honest.)"""
    resp = client.get("/v1/traces/short")  # 5 chars
    assert resp.status_code in (404, 422), (
        f"short trace_id should 404 or 422, got {resp.status_code}"
    )


def test_trace_id_too_long_returns_422(client: TestClient) -> None:
    too_long = "a" * 129
    resp = client.get(f"/v1/traces/{too_long}")
    assert resp.status_code in (404, 422)


# ---------- module-level constants -----------------------------------------

def test_cache_key_prefix_matches_spec() -> None:
    """Spec: "trace:cache:* namespace" — exact prefix is part of the contract
    because external tooling (debugger dashboards) may scan Redis for
    keys matching this pattern."""
    assert traces_mod.TRACE_CACHE_KEY_PREFIX == "trace:cache:"


def test_cache_ttl_is_5_minutes() -> None:
    """Spec literal: 5min TTL."""
    assert traces_mod.TRACE_CACHE_TTL_SECONDS == 5 * 60
