"""Retry helper for the workflow execution engine.

The 4-boundary error model (eng-review finding #9) maps cleanly to
retry semantics:

- Boundary #2 (runtime / LLM 5xx / timeout / rate-limit) -> **retryable**
  with indexed backoff. 1s after first attempt, 2s after second.
- Boundary #3 (user / 参数不全) -> **never retry**. The user must fix
  the workflow definition; retrying just wastes time.
- Boundary #4 (security / 未授权凭证) -> **never retry**. A 403 will
  not become a 200 with more attempts.

This module implements that policy. The default ``retry_count=1``
means "one retry, total 2 attempts" — the spec's MVP retry budget.
"""
from __future__ import annotations

import asyncio

from app.errors.classes import SecurityError, UserError


async def with_retry(fn, retry_count: int = 1):
    """Run an async function with the workflow retry policy.

    Args:
        fn: Zero-arg async callable. Called once per attempt.
        retry_count: Number of *retries* (not total attempts). Default 1
            -> up to 2 attempts total.

    Returns:
        Whatever ``fn()`` returns on the first successful attempt.

    Raises:
        UserError, SecurityError: re-raised immediately, no retry.
        Exception: the last one, after all retries are exhausted.
    """
    last_exc: BaseException | None = None
    for attempt in range(retry_count + 1):
        try:
            return await fn()
        except (UserError, SecurityError):
            # Boundary #3 + #4: do not retry user / security errors.
            raise
        except Exception as e:
            last_exc = e
            if attempt < retry_count:
                # Indexed backoff: 1s, 2s, 4s, ...
                await asyncio.sleep(1 * (2 ** attempt))
    assert last_exc is not None  # always set when we exit the loop
    raise last_exc


__all__ = ["with_retry"]
