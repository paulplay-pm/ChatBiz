"""Unit tests for ``app.rate_limit`` — Redis-backed reveal rate limiter."""

from __future__ import annotations

import pytest
from fakeredis import aioredis

from app.rate_limit import (
    REVEAL_LIMIT_PER_MINUTE,
    WINDOW_SECONDS,
    RateLimitExceededError,
    check_reveal_quota,
)


@pytest.fixture
async def redis() -> aioredis.FakeRedis:
    """Create a fresh fakeredis instance per test."""
    r = aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


@pytest.mark.asyncio
class TestCheckRevealQuota:
    async def test_first_call_does_not_raise(self, redis: aioredis.FakeRedis) -> None:
        await check_reveal_quota(redis, "user-1")
        # First call sets expire, no exception.

    async def test_up_to_limit_does_not_raise(
        self, redis: aioredis.FakeRedis
    ) -> None:
        for _ in range(REVEAL_LIMIT_PER_MINUTE):
            await check_reveal_quota(redis, "user-1")
        # 10 calls, none should fail.

    async def test_eleventh_call_raises(self, redis: aioredis.FakeRedis) -> None:
        for _ in range(REVEAL_LIMIT_PER_MINUTE):
            await check_reveal_quota(redis, "user-1")

        with pytest.raises(RateLimitExceededError) as exc_info:
            await check_reveal_quota(redis, "user-1")
        assert exc_info.value.retry_after_seconds > 0

    async def test_retry_after_is_positive(self, redis: aioredis.FakeRedis) -> None:
        for _ in range(REVEAL_LIMIT_PER_MINUTE):
            await check_reveal_quota(redis, "user-1")

        with pytest.raises(RateLimitExceededError) as exc_info:
            await check_reveal_quota(redis, "user-1")
        assert exc_info.value.retry_after_seconds >= 1

    async def test_per_user_isolation(self, redis: aioredis.FakeRedis) -> None:
        # User 1 exhausts their limit.
        for _ in range(REVEAL_LIMIT_PER_MINUTE):
            await check_reveal_quota(redis, "user-1")

        with pytest.raises(RateLimitExceededError):
            await check_reveal_quota(redis, "user-1")

        # User 2 is unaffected.
        for _ in range(REVEAL_LIMIT_PER_MINUTE):
            await check_reveal_quota(redis, "user-2")
        # Should not raise.

    async def test_count_resets_after_expiry(
        self, redis: aioredis.FakeRedis
    ) -> None:
        """After the key expires, the counter resets."""
        key = "ratelimit:reveal:user-1"
        for _ in range(REVEAL_LIMIT_PER_MINUTE):
            await check_reveal_quota(redis, "user-1")

        with pytest.raises(RateLimitExceededError):
            await check_reveal_quota(redis, "user-1")

        # Manually delete the key to simulate expiry.
        await redis.delete(key)

        # Now the counter is back to 1.
        await check_reveal_quota(redis, "user-1")
        # Should not raise.

    async def test_ttl_negative_fallback_defaults_to_window(
        self, redis: aioredis.FakeRedis
    ) -> None:
        """When ttl < 0 (key without expire), fallback to WINDOW_SECONDS."""
        key = "ratelimit:reveal:user-ttl"

        # Simulate: key already exists at count > limit with expired TTL (ttl = -1)
        await redis.set(key, REVEAL_LIMIT_PER_MINUTE + 1)
        # Don't set expire — so ttl() returns -1.

        with pytest.raises(RateLimitExceededError) as exc_info:
            await check_reveal_quota(redis, "user-ttl")
        assert exc_info.value.retry_after_seconds == WINDOW_SECONDS


@pytest.mark.asyncio
class TestRateLimitExceededError:
    async def test_minimum_retry_after_is_1(self) -> None:
        exc = RateLimitExceededError(retry_after_seconds=0)
        assert exc.retry_after_seconds == 1

    async def test_str_contains_retry_info(self) -> None:
        exc = RateLimitExceededError(retry_after_seconds=42)
        assert "retry after 42s" in str(exc)
