"""Coverage-gap tests for app/routing/table.py (task A.2 of coverage_improvement).

Per retrospective §6 of gateway-egress-enforcement-p0, this file
fills the 36% coverage gap on `routing/table.py` by exercising the
Redis pipeline write path, the Redis read path, and the in-memory
fallback when Redis is down.

Why a separate file: the existing test_routing_*.py suites cover
happy paths and edge cases. This file is **only** about pushing
coverage numbers, not adding behaviour tests. If a future refactor
re-orders statements, the line numbers in `verify-coverage.txt` may
shift but the tests still pass.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routing import table as routing_table
from app.routing.table import get_routing, load_routing_into_cache, reset_inmemory_for_tests


@pytest.fixture(autouse=True)
def _reset_inmemory_between_tests():
    """Each test gets a clean in-memory cache to avoid bleed-over."""
    reset_inmemory_for_tests()
    yield
    reset_inmemory_for_tests()


# ---------- load_routing_into_cache: PG happy path + Redis write -------

@pytest.mark.asyncio
async def test_load_routing_populates_inmemory_and_redis_pipeline() -> None:
    """All enabled ModelRouting rows go into the in-memory dict and
    into Redis via a single pipeline.execute()."""
    rows = [
        SimpleNamespace(
            model_name="qwen-max", model_kind="public",
            upstream_base_url="http://upstream.example.com",
            upstream_path="/v1/chat/completions", timeout_ms=30000,
        ),
        SimpleNamespace(
            model_name="internal-vllm", model_kind="private",
            upstream_base_url="http://internal.example.com",
            upstream_path="/v1/chat/completions", timeout_ms=60000,
        ),
    ]

    fake_redis = MagicMock()
    pipe = MagicMock()
    pipe.execute = AsyncMock(return_value=[])
    fake_redis.pipeline = MagicMock(return_value=pipe)

    fake_session = MagicMock()
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)
    fake_result = MagicMock()
    fake_result.scalars.return_value.all.return_value = rows
    fake_session.execute = AsyncMock(return_value=fake_result)

    with (
        patch("app.routing.table.get_session", return_value=fake_session),
        patch("app.routing.table.redis_client.get_redis", return_value=fake_redis),
        patch("app.routing.table.get_settings") as mock_settings,
    ):
        mock_settings.return_value.routing_table_ttl_seconds = 60
        count = await load_routing_into_cache()

    assert count == 2
    # The pipeline was called with the right commands
    pipe.set.assert_any_call(
        "routing:model:qwen-max",
        json.dumps({
            "model_kind": "public",
            "upstream_base_url": "http://upstream.example.com",
            "upstream_path": "/v1/chat/completions",
            "timeout_ms": 30000,
        }),
        ex=60,
    )
    pipe.set.assert_any_call(
        "routing:model:internal-vllm",
        json.dumps({
            "model_kind": "private",
            "upstream_base_url": "http://internal.example.com",
            "upstream_path": "/v1/chat/completions",
            "timeout_ms": 60000,
        }),
        ex=60,
    )
    pipe.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_load_routing_continues_when_redis_write_fails() -> None:
    """If Redis pipeline.execute() raises, the in-memory dict is
    still populated and the function still returns the count (just
    with a warning logged)."""
    rows = [
        SimpleNamespace(
            model_name="qwen-max", model_kind="public",
            upstream_base_url="http://upstream.example.com",
            upstream_path="/v1/chat/completions", timeout_ms=30000,
        ),
    ]
    fake_redis = MagicMock()
    pipe = MagicMock()
    pipe.execute = AsyncMock(side_effect=ConnectionError("simulated Redis down"))
    fake_redis.pipeline = MagicMock(return_value=pipe)
    fake_session = MagicMock()
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)
    fake_result = MagicMock()
    fake_result.scalars.return_value.all.return_value = rows
    fake_session.execute = AsyncMock(return_value=fake_result)

    with (
        patch("app.routing.table.get_session", return_value=fake_session),
        patch("app.routing.table.redis_client.get_redis", return_value=fake_redis),
        patch("app.routing.table.get_settings") as mock_settings,
    ):
        mock_settings.return_value.routing_table_ttl_seconds = 60
        count = await load_routing_into_cache()

    # Function still returns the count of in-memory entries
    assert count == 1
    # The model is in the in-memory dict
    from app.routing.table import _inmemory
    assert "qwen-max" in _inmemory
    assert _inmemory["qwen-max"]["model_kind"] == "public"


# ---------- get_routing: Redis hit + miss + Redis-down fallback -----------

@pytest.mark.asyncio
async def test_get_routing_redis_hit_returns_cached_entry() -> None:
    """Fast path: Redis returns a JSON-serialised entry, get_routing
    parses it and returns the dict."""
    cached = {
        "model_kind": "public",
        "upstream_base_url": "http://upstream.example.com",
        "upstream_path": "/v1/chat/completions",
        "timeout_ms": 30000,
    }
    fake_redis = MagicMock()
    fake_redis.get = AsyncMock(return_value=json.dumps(cached))
    with patch("app.routing.table.redis_client.get_redis", return_value=fake_redis):
        result = await get_routing("qwen-max")

    assert result == cached


@pytest.mark.asyncio
async def test_get_routing_redis_miss_falls_through_to_inmemory() -> None:
    """Redis returns None — get_routing falls through to the
    in-memory dict, which was populated at startup."""
    from app.routing.table import _inmemory
    _inmemory["qwen-max"] = {
        "model_kind": "public",
        "upstream_base_url": "http://upstream.example.com",
        "upstream_path": "/v1/chat/completions",
        "timeout_ms": 30000,
    }
    fake_redis = MagicMock()
    fake_redis.get = AsyncMock(return_value=None)
    with patch("app.routing.table.redis_client.get_redis", return_value=fake_redis):
        result = await get_routing("qwen-max")

    assert result is not None
    assert result["model_kind"] == "public"


@pytest.mark.asyncio
async def test_get_routing_redis_down_falls_through_to_inmemory() -> None:
    """If Redis raises (connection refused, timeout), get_routing
    logs a warning and returns the in-memory entry rather than
    failing the whole request."""
    from app.routing.table import _inmemory
    _inmemory["qwen-max"] = {
        "model_kind": "public",
        "upstream_base_url": "http://upstream.example.com",
        "upstream_path": "/v1/chat/completions",
        "timeout_ms": 30000,
    }
    fake_redis = MagicMock()
    fake_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
    with patch("app.routing.table.redis_client.get_redis", return_value=fake_redis):
        result = await get_routing("qwen-max")

    assert result is not None
    assert result["model_kind"] == "public"


@pytest.mark.asyncio
async def test_get_routing_unknown_model_returns_none() -> None:
    """If neither Redis nor in-memory knows the model, return None
    (caller raises RoutingError → 400)."""
    fake_redis = MagicMock()
    fake_redis.get = AsyncMock(return_value=None)
    with patch("app.routing.table.redis_client.get_redis", return_value=fake_redis):
        result = await get_routing("totally-unknown-model")

    assert result is None


@pytest.mark.asyncio
async def test_get_routing_redis_returns_garbage_falls_through() -> None:
    """If Redis returns a non-JSON value (e.g. someone wrote a raw
    string by mistake), the JSON parse error is caught internally
    and the function returns None (caller raises RoutingError →
    400). This is the resilience path that protects against
    partial-cache corruption — silently propagating JSONDecodeError
    to the chat endpoint would 502 every request, not 400.
    """
    fake_redis = MagicMock()
    fake_redis.get = AsyncMock(return_value="not-valid-json")
    with patch("app.routing.table.redis_client.get_redis", return_value=fake_redis):
        # Implementation catches JSONDecodeError and returns None
        # (without falling through to in-memory, because a corrupt
        # cache is a different failure mode than a missing one).
        result = await get_routing("qwen-max")

    assert result is None


# Local import for SimpleNamespace (the parent test infra uses
# `from types import SimpleNamespace` at the top in other files;
# doing it locally here keeps the file self-contained).
from types import SimpleNamespace
