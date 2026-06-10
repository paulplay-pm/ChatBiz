"""Integration tests for the routing table cache (Redis + in-memory).

Three things under test:

* ``load_routing_into_cache`` reads enabled rows from the database
  and populates both Redis and the in-process dict. The DB call is
  mocked (no real Postgres in CI); we hand ``get_session`` a
  canned ``AsyncMock`` that returns a single routing row.
* ``get_routing`` hits Redis first; if Redis is empty or down, it
  falls back to the in-memory dict.
* When Redis is unreachable, ``load_routing_into_cache`` still
  completes (with the in-memory dict populated) so the gateway
  can serve a request during a Redis blip.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis

from app import redis_client
from app.routing import table as routing_table
from app.routing.table import get_routing, load_routing_into_cache


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_fake_routing_row(model_name: str, model_kind: str, base_url: str):
    """Build a SQLAlchemy-like object the loader can read attrs from."""
    row = MagicMock()
    row.model_name = model_name
    row.model_kind = model_kind
    row.upstream_base_url = base_url
    row.upstream_path = "/v1/chat/completions"
    row.timeout_ms = 30000
    return row


class TestRoutingTable(unittest.TestCase):
    """Routing table loader + resolver behaviour."""

    def setUp(self):
        # Replace the real Redis with a fakeredis instance.
        redis_client.reset_pool_for_tests()
        self._fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
        self._original_get_redis = redis_client.get_redis
        redis_client.get_redis = lambda: self._fake
        # Always start with a clean in-memory dict.
        routing_table.reset_inmemory_for_tests()

    def tearDown(self):
        redis_client.get_redis = self._original_get_redis
        redis_client.reset_pool_for_tests()
        routing_table.reset_inmemory_for_tests()
        _run(self._fake.aclose())

    def _patch_session(self, rows):
        """Patch ``app.routing.table.get_session`` to return a fake
        session that yields ``rows`` for the routing SELECT.

        The real ``get_session`` is an async context manager; we
        replace it with one that yields an ``AsyncMock`` whose
        ``execute()`` returns a result object whose ``scalars().all()``
        is the row list.
        """
        session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = rows
        session.execute.return_value = result
        # Also support the ``async with`` context manager protocol.
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        return patch("app.routing.table.get_session", return_value=session)

    def test_load_populates_both_caches(self):
        rows = [
            _make_fake_routing_row("qwen-max", "public", "https://dashscope.aliyuncs.com"),
            _make_fake_routing_row("internal-vllm-qwen", "private", "http://vllm.internal:8000"),
        ]
        with self._patch_session(rows):
            count = _run(load_routing_into_cache())
        self.assertEqual(count, 2)
        # In-memory dict has both models
        self.assertIn("qwen-max", routing_table._inmemory)
        self.assertIn("internal-vllm-qwen", routing_table._inmemory)
        # Redis has both models under the routing:model: prefix
        raw = _run(self._fake.get("routing:model:qwen-max"))
        self.assertIsNotNone(raw)
        self.assertIn("dashscope", raw)

    def test_get_routing_redis_path(self):
        rows = [
            _make_fake_routing_row("qwen-max", "public", "https://dashscope.aliyuncs.com"),
        ]
        with self._patch_session(rows):
            _run(load_routing_into_cache())
        # Direct Redis lookup works
        entry = _run(get_routing("qwen-max"))
        self.assertEqual(entry["upstream_base_url"], "https://dashscope.aliyuncs.com")
        self.assertEqual(entry["model_kind"], "public")

    def test_get_routing_inmemory_fallback(self):
        # Manually populate the in-memory dict without touching Redis
        routing_table._inmemory["test-model"] = {
            "model_kind": "public",
            "upstream_base_url": "http://test",
            "upstream_path": "/v1/chat/completions",
            "timeout_ms": 30000,
        }
        # Clear Redis to force the fallback path
        _run(self._fake.flushdb())
        entry = _run(get_routing("test-model"))
        self.assertEqual(entry["upstream_base_url"], "http://test")

    def test_get_routing_unknown_returns_none(self):
        entry = _run(get_routing("not-in-table"))
        self.assertIsNone(entry)

    def test_redis_outage_falls_back_to_inmemory(self):
        """If Redis throws on read, get_routing returns the
        in-memory dict's entry."""
        # Populate the in-memory dict
        routing_table._inmemory["fallback-model"] = {
            "model_kind": "public",
            "upstream_base_url": "http://fallback",
            "upstream_path": "/v1/chat/completions",
            "timeout_ms": 30000,
        }
        # Substitute a Redis client that throws
        class BrokenRedis:
            async def get(self, key):
                raise RuntimeError("redis down")

        original = redis_client.get_redis
        redis_client.get_redis = lambda: BrokenRedis()
        try:
            entry = _run(get_routing("fallback-model"))
        finally:
            redis_client.get_redis = original
        self.assertEqual(entry["upstream_base_url"], "http://fallback")

    def test_load_with_redis_outage_still_populates_inmemory(self):
        """``load_routing_into_cache`` should not fail when Redis is
        down — the in-memory dict is the source of truth in that
        mode, and the gateway must still be able to serve traffic.
        """
        rows = [
            _make_fake_routing_row("qwen-max", "public", "https://dashscope.aliyuncs.com"),
        ]
        # Substitute a Redis client whose pipeline().execute() raises
        class BrokenPipeline:
            def set(self, *a, **kw):
                return self

            async def execute(self):
                raise RuntimeError("redis down at startup")

        class BrokenRedis:
            def pipeline(self):
                return BrokenPipeline()

        original = redis_client.get_redis
        redis_client.get_redis = lambda: BrokenRedis()
        try:
            with self._patch_session(rows):
                count = _run(load_routing_into_cache())
        finally:
            redis_client.get_redis = original
        # load() still returns the row count, and the in-memory
        # dict is populated.
        self.assertEqual(count, 1)
        self.assertIn("qwen-max", routing_table._inmemory)


if __name__ == "__main__":
    unittest.main()
