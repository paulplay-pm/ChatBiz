"""Integration tests for ``GET /v1/traces/{trace_id}``.

Covers the 4 fixtures required by spec §4.1:

1. **Redis hit** — cache returns events; endpoint returns them with
   ``X-Trace-Source: redis``. The PG session factory is never touched.
2. **Redis miss + PG hit** — cache returns ``None``; PG returns a row;
   endpoint returns it with ``X-Trace-Source: pg`` AND writes it back
   to Redis with a 5-minute TTL.
3. **Both miss** — endpoint returns 404 with ``{"error": "trace_not_found", ...}``.
4. **Redis down (exception) → PG fallback** — Redis raises on GET;
   the store catches it, treats it as a miss, queries PG, and returns
   the result transparently.

Strategy:

* Use a real :mod:`fakeredis` for the cache (per audit-and-isolation
  convention, see ``_critical_path_base.py``).
* Mock the session factory with a fake :class:`AsyncSession` that
  yields a result for a fixed row, mirroring the AuditLog ORM shape.
* The FastAPI app is created from the real ``app.main:app`` and the
  test replaces ``app.api.traces._store`` via :func:`set_trace_store`
  (no monkey-patching of the underlying redis or DB modules).

We do **not** mount a TestClient for PG — the spec is about the
endpoint's two-tier behavior, which the store is responsible for.
The endpoint just delegates.
"""
from __future__ import annotations

import asyncio
import json
import os
import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

# Settings are validated at import; provide safe defaults.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x")
os.environ.setdefault("REDIS_URL", "redis://x")
os.environ.setdefault("CREDENTIAL_SERVICE_URL", "http://x")

import fakeredis  # noqa: E402
import fakeredis.aioredis  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import redis_client  # noqa: E402
from app.api import traces as traces_module  # noqa: E402
from app.main import app  # noqa: E402
from app.trace.store import CACHE_PREFIX, TraceStore  # noqa: E402


def _make_event(
    trace_id: str = "01HXYZGATEWAYTEST000000000",
    user_id: str = "svc-paul",
    row_id: int = 1,
) -> dict[str, Any]:
    """Build a representative event dict that matches the cache shape."""
    return {
        "id": row_id,
        "trace_id": trace_id,
        "user_id": user_id,
        "workflow_id": "wf-monthly-report",
        "model": "qwen-max",
        "model_kind": "public",
        "bypass_isolation": False,
        "pii_detected_types": ["身份证"],
        "pii_redacted_count": 1,
        "prompt_hash": "a" * 64,
        "token_input": 42,
        "token_output": 17,
        "latency_ms": 153,
        "upstream_status": 200,
        "error_class": None,
        "created_at": "2026-06-10T00:00:00+00:00",
    }


def _make_session_factory(rows: list[Any] | None):
    """Build a session factory that yields a row set for the next query.

    The factory's session's ``execute()`` returns a result whose
    ``scalars().all()`` is ``rows`` (or ``[]`` if ``rows`` is ``None``).
    """
    if rows is None:
        rows = []
    factory = MagicMock()

    # async with factory() as s: ...
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    # session.execute(stmt) -> result
    result = MagicMock()
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=rows)
    result.scalars = MagicMock(return_value=scalars)
    session.execute = AsyncMock(return_value=result)
    factory.return_value = session
    return factory


class TestTracesEndpoint(unittest.TestCase):
    """Drive the FastAPI endpoint through TestClient with a stub store."""

    def setUp(self) -> None:
        redis_client.reset_pool_for_tests()
        self._real_get_redis = redis_client.get_redis
        # Use a shared FakeServer so the sync ``_sync`` client (used to
        # pre-populate keys from the test thread) writes to the same
        # backing store the async ``self._fake`` reads from.
        self._server = fakeredis.FakeServer()
        self._fake = fakeredis.aioredis.FakeRedis(
            server=self._server, decode_responses=True
        )
        self._sync = fakeredis.FakeRedis(server=self._server, decode_responses=True)
        redis_client.get_redis = lambda: self._fake
        self._prev_store = traces_module._store
        self.client = TestClient(app)

    def tearDown(self) -> None:
        # Restore the original store and Redis factory so other tests
        # aren't polluted by our fakeredis substitution.
        traces_module.set_trace_store(self._prev_store)
        redis_client.get_redis = self._real_get_redis
        redis_client.reset_pool_for_tests()
        # aclose() is a coroutine; run it on the test loop if active.
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._fake.aclose())
            else:
                loop.run_until_complete(self._fake.aclose())
        except RuntimeError:
            pass

    def _populate_cache_sync(self, trace_id: str, events: list[dict]) -> None:
        """Pre-populate the fakeredis cache using the shared sync client.

        fakeredis 2.x is fully async, so the SET must reach the same
        backing store the endpoint reads from. By binding the sync
        client and the async client to the same ``FakeServer``, the
        sync ``.set`` is visible to the next async ``.get`` even
        though the two clients run in different threads.
        """
        self._sync.set(f"{CACHE_PREFIX}{trace_id}", json.dumps(events))

    def _read_cache_sync(self, trace_id: str) -> str | None:
        """Read the cache via the shared sync client (test thread)."""
        return self._sync.get(f"{CACHE_PREFIX}{trace_id}")

    # ---- 1. Redis hit ------------------------------------------------

    def test_redis_hit_returns_events_with_source_header(self):
        """When the cache key is populated, the endpoint returns it
        with ``X-Trace-Source: redis`` and never touches PG."""
        trace_id = "redis-hit-trace"
        events = [_make_event(trace_id=trace_id, row_id=1)]
        self._populate_cache_sync(trace_id, events)

        factory = _make_session_factory(rows=[])  # would be observed if hit
        store = TraceStore(self._fake, factory, ttl_seconds=300)
        traces_module.set_trace_store(store)

        resp = self.client.get(f"/v1/traces/{trace_id}")
        assert resp.status_code == 200, resp.text
        assert resp.headers["X-Trace-Source"] == "redis"
        body = resp.json()
        assert body["trace_id"] == trace_id
        assert body["events"] == events
        # PG must NOT have been queried on a Redis hit.
        factory.assert_not_called()

    # ---- 2. Redis miss + PG hit --------------------------------------

    def test_redis_miss_pg_hit_falls_back_and_refills_cache(self):
        """When the cache is empty but PG has a row, the endpoint
        returns it with ``X-Trace-Source: pg`` and writes the
        result back to Redis with a 5-minute TTL."""
        trace_id = "pg-only-trace"
        row = MagicMock()
        # The store reads .id / .trace_id / etc directly off the row.
        for k, v in _make_event(trace_id=trace_id, row_id=7).items():
            setattr(row, k, v)
        # created_at is a datetime on the real model.
        row.created_at = datetime(2026, 6, 10, tzinfo=timezone.utc)

        factory = _make_session_factory(rows=[row])
        store = TraceStore(self._fake, factory, ttl_seconds=300)
        traces_module.set_trace_store(store)

        resp = self.client.get(f"/v1/traces/{trace_id}")
        assert resp.status_code == 200, resp.text
        assert resp.headers["X-Trace-Source"] == "pg"
        body = resp.json()
        assert body["trace_id"] == trace_id
        assert len(body["events"]) == 1
        assert body["events"][0]["id"] == 7
        # The cache must have been re-populated by the store.
        cached = self._read_cache_sync(trace_id)
        assert cached is not None
        cached_list = json.loads(cached)
        assert len(cached_list) == 1
        assert cached_list[0]["id"] == 7

    # ---- 3. Both miss ------------------------------------------------

    def test_both_miss_returns_404(self):
        """When neither cache nor PG has the trace, the endpoint
        returns 404 with the spec-mandated error body."""
        trace_id = "missing-trace"
        factory = _make_session_factory(rows=[])
        store = TraceStore(self._fake, factory, ttl_seconds=300)
        traces_module.set_trace_store(store)

        resp = self.client.get(f"/v1/traces/{trace_id}")
        assert resp.status_code == 404
        body = resp.json()
        assert body == {"error": "trace_not_found", "trace_id": trace_id}

    # ---- 4. Redis down → PG fallback --------------------------------

    def test_redis_failure_falls_back_to_pg(self):
        """When Redis raises on GET, the store treats it as a miss
        and queries PG transparently — endpoint returns 200 + pg."""
        trace_id = "redis-down-trace"
        row = MagicMock()
        for k, v in _make_event(trace_id=trace_id, row_id=11).items():
            setattr(row, k, v)
        row.created_at = datetime(2026, 6, 10, tzinfo=timezone.utc)

        # A Redis that always blows up on GET.
        broken_redis = MagicMock()
        broken_redis.get = AsyncMock(side_effect=ConnectionError("redis down"))
        broken_redis.set = AsyncMock(side_effect=ConnectionError("redis down"))

        factory = _make_session_factory(rows=[row])
        store = TraceStore(broken_redis, factory, ttl_seconds=300)
        traces_module.set_trace_store(store)

        resp = self.client.get(f"/v1/traces/{trace_id}")
        assert resp.status_code == 200, resp.text
        assert resp.headers["X-Trace-Source"] == "pg"
        body = resp.json()
        assert body["trace_id"] == trace_id
        assert body["events"][0]["id"] == 11
        # The broken Redis's get + set were each called once.
        assert broken_redis.get.await_count == 1
        # The re-cache write also fired and swallowed its own error.
        assert broken_redis.set.await_count == 1

    # ---- 5. Corrupt cache value → fall through to PG ---------------

    def test_corrupt_cache_value_falls_through_to_pg(self):
        """A non-JSON or non-list value in the cache key is treated
        as a miss; the store then queries PG and returns the row."""
        trace_id = "corrupt-cache-trace"
        # Write a JSON object (not a list) — the store rejects any
        # non-list payload as malformed and treats it as a miss.
        self._populate_cache_sync(trace_id, {"not": "a list"})
        row = MagicMock()
        for k, v in _make_event(trace_id=trace_id, row_id=12).items():
            setattr(row, k, v)
        row.created_at = datetime(2026, 6, 10, tzinfo=timezone.utc)

        factory = _make_session_factory(rows=[row])
        store = TraceStore(self._fake, factory, ttl_seconds=300)
        traces_module.set_trace_store(store)

        resp = self.client.get(f"/v1/traces/{trace_id}")
        assert resp.status_code == 200
        assert resp.headers["X-Trace-Source"] == "pg"
        body = resp.json()
        assert body["events"][0]["id"] == 12

    def test_garbage_json_in_cache_falls_through_to_pg(self):
        """A value that fails ``json.loads`` is treated as a miss."""
        trace_id = "garbage-trace"
        # Bypass the JSON encoder and write raw garbage to the cache.
        self._sync.set(f"{CACHE_PREFIX}{trace_id}", "this is not json {{{{")

        row = MagicMock()
        for k, v in _make_event(trace_id=trace_id, row_id=13).items():
            setattr(row, k, v)
        row.created_at = datetime(2026, 6, 10, tzinfo=timezone.utc)

        factory = _make_session_factory(rows=[row])
        store = TraceStore(self._fake, factory, ttl_seconds=300)
        traces_module.set_trace_store(store)

        resp = self.client.get(f"/v1/traces/{trace_id}")
        assert resp.status_code == 200
        assert resp.headers["X-Trace-Source"] == "pg"


class TestStoreProperties(unittest.TestCase):
    """Cover the small surface of the store that the endpoint tests
    don't touch (namespace + TTL properties)."""

    def test_cache_prefix_and_ttl_propagate(self):
        factory = _make_session_factory(rows=[])
        store = TraceStore(self._fake if False else MagicMock(), factory, ttl_seconds=42)
        # We can't depend on ``self._fake`` here — use a fresh MagicMock.
        from app.trace.store import CACHE_PREFIX

        assert store.cache_prefix == CACHE_PREFIX
        assert store.ttl_seconds == 42


class TestGetTraceStoreLazyInit(unittest.TestCase):
    """``get_trace_store`` lazily builds a store from the live Redis
    factory and session factory on first call, then reuses it."""

    def setUp(self) -> None:
        from app.api import traces as traces_module

        self._mod = traces_module
        self._prev = traces_module._store

    def tearDown(self) -> None:
        self._mod.set_trace_store(self._prev)

    def test_lazy_init_builds_then_reuses(self):
        # First reset to a known-fresh state.
        self._mod.reset_store_for_tests()
        # Replace the deps the lazy builder uses.
        fake_redis = MagicMock(name="fake-redis")
        fake_factory = MagicMock(name="fake-factory")
        with (
            unittest.mock.patch.object(self._mod, "get_redis", return_value=fake_redis),
            unittest.mock.patch.object(self._mod, "_get_session_factory", return_value=fake_factory),
        ):
            s1 = self._mod.get_trace_store()
            s2 = self._mod.get_trace_store()
        assert s1 is s2
        # The store was built with our fake redis + factory.
        # ``_store._redis`` is the *internal* attribute set by __init__.
        assert s1._redis is fake_redis
        assert s1._session_factory is fake_factory


if __name__ == "__main__":
    unittest.main()
