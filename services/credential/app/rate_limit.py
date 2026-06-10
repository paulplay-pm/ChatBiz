"""Per-user, per-minute token-bucket rate limiter (Redis-backed).

Spec §凭证使用频率限制: ``reveal`` API is capped at **10 calls per
user per minute**; the 11th call inside the same 60-second window MUST
return HTTP 429 with a ``Retry-After`` header.

Implementation
--------------
Classic Redis ``INCR`` / ``EXPIRE`` pattern:

* ``INCR ratelimit:reveal:{user_id}`` returns the new counter value.
* On the **first** increment (counter == 1) we ``EXPIRE`` the key with
  a 60-second TTL — subsequent increments preserve the TTL so the
  window is *fixed* (not sliding).
* If the counter exceeds the limit we read the remaining TTL and raise
  ``RateLimitExceededError`` carrying ``retry_after_seconds``.

The fixed-window approach was chosen over a sliding window for MVP
simplicity (no Lua script needed); it is the model documented in the
official Redis docs ("Pattern: Rate limiter 2"). The 60 s window leaves
no real attack surface — a caller can at worst sneak the next window's
quota in immediately after the first window's last call.

The interface is async — built on ``redis.asyncio`` — so it slots into
FastAPI's dependency-injection graph without spawning sync threads.

Tests inject a ``fakeredis.aioredis.FakeRedis`` instance through the
same ``get_redis`` override mechanism the production app uses, so the
limiter is exercised end-to-end without a live Redis container.
"""

from __future__ import annotations

from typing import Final, Protocol

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Per spec §凭证使用频率限制.
REVEAL_LIMIT_PER_MINUTE: Final = 10

#: Fixed-window length in seconds.
WINDOW_SECONDS: Final = 60

#: Key prefix; the {user_id} suffix scopes the counter to one user.
_KEY_PREFIX: Final = "ratelimit:reveal:"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RateLimitExceededError(Exception):
    """Raised when a user exceeds the reveal-call quota.

    The HTTP layer (``app.main``) maps this to a 429 response with the
    ``Retry-After`` header populated from ``retry_after_seconds``.
    """

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = max(retry_after_seconds, 1)
        super().__init__(
            f"reveal rate limit exceeded; retry after {self.retry_after_seconds}s"
        )


# ---------------------------------------------------------------------------
# Redis client protocol (lets tests inject fakeredis)
# ---------------------------------------------------------------------------


class RedisLike(Protocol):
    """Minimal subset of ``redis.asyncio.Redis`` the limiter actually uses."""

    async def incr(self, name: str) -> int: ...
    async def expire(self, name: str, time: int) -> bool: ...
    async def ttl(self, name: str) -> int: ...


# ---------------------------------------------------------------------------
# Core implementation
# ---------------------------------------------------------------------------


async def check_reveal_quota(redis: RedisLike, user_id: str) -> None:
    """Increment the per-user counter; raise on the 11th call.

    The function performs three Redis commands in the worst case
    (incr → expire → ttl) and one in the best case (incr).  All three
    are O(1); the round-trip cost dominates and is in the < 1 ms range
    against a local Redis.
    """
    key = _KEY_PREFIX + user_id
    count = await redis.incr(key)
    if count == 1:
        # First call in the window: prime the TTL so the counter
        # eventually resets. Subsequent calls inherit this TTL.
        await redis.expire(key, WINDOW_SECONDS)
    if count > REVEAL_LIMIT_PER_MINUTE:
        # Use ``ttl`` so the Retry-After we hand back is honest about
        # how long until the bucket actually refills.
        ttl = await redis.ttl(key)
        # ``ttl == -1`` means the key has no TTL (shouldn't happen, but
        # defend against it). ``ttl == -2`` means the key vanished
        # between the INCR and the TTL (only possible if Redis was
        # flushed mid-call). Default to the full window in either case.
        if ttl < 0:
            ttl = WINDOW_SECONDS
        raise RateLimitExceededError(retry_after_seconds=ttl)


__all__ = [
    "REVEAL_LIMIT_PER_MINUTE",
    "WINDOW_SECONDS",
    "RateLimitExceededError",
    "RedisLike",
    "check_reveal_quota",
]
