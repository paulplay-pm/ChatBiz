"""Client-side HA failover retry with idempotency key.

Spec source: ``openspec/changes/gateway-egress-enforcement-p0/specs/gateway-ha-topology/spec.md``
requirement "客户端 SDK 必须实现 `RetryWithIdempotency` 装饰器" (D3 in design.md).

Behaviour the spec locks in:

* ``Idempotency-Key`` = ``SHA-256(user_id + body_hash + 5min_timestamp_bucket)``
  where ``body_hash`` is ``SHA-256(json.dumps(body, sort_keys=True))`` and the
  bucket is ``int(time.time()) // 300``. Keys are stable across all retries
  that happen inside the same 5-minute window — that's the whole point: the
  upstream uses the key to de-duplicate.
* Retries **only** fire on (a) the explicit ``HAFailoverError`` (the
  gateway's 503 ``HA_FAILOVER`` signal) and (b) ``ConnectionError``
  (transport-level hiccup while the upstream instance is being drained).
* 5xx that is **not** a 503 ``HA_FAILOVER`` (``500`` / ``502`` / ``504`` …)
  is **not** retried here — those are owned by ``app.llm.client``'s
  existing one-shot 5xx retry. Stacking a second retry layer on top would
  multiply upstream load (see design.md R1).
* 5s total budget, 3 attempts max.
* Raises ``HAFailoverExhausted`` after the 3rd attempt fails.

This module is intentionally **independent** of ``app.llm.client`` so any
async function — not just the LLM upstream — can be wrapped with the
same idempotent retry semantics (e.g. a future credential-service call
that also fronts the same NGINX L4 LB).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any, Awaitable, Callable


class HAFailoverError(Exception):
    """Raised when the upstream returns 503 HA_FAILOVER or equivalent.

    The decorator treats this as a retryable signal. The ``status_code``
    attribute lets callers (and tests) distinguish a true ``HA_FAILOVER``
    from a generic 5xx — only ``503`` should trigger the retry path.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class HAFailoverExhausted(Exception):
    """Raised when the 3 retry attempts within the window all fail.

    The spec wants the caller to surface a typed error so the API layer
    can map it to a 503 response (gateway is genuinely unavailable, not
    the caller's fault).
    """

    def __init__(self, message: str, *, attempts: int) -> None:
        super().__init__(message)
        self.attempts = attempts


def _body_hash(body: Any) -> str:
    """Stable SHA-256 of a JSON-serialisable body.

    ``sort_keys=True`` + ``separators=(",", ":")`` make the hash independent
    of dict ordering and whitespace — two clients serialising the same body
    with different Python ``dict`` layouts still produce the same key.
    """

    serialised = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def compute_idempotency_key(user_id: str, body: Any, timestamp: float | None = None) -> str:
    """Compute the Idempotency-Key for a request.

    Formula: ``SHA-256(user_id + body_hash + 5min_bucket)``.

    The 5-minute bucket (``timestamp // 300``) is what makes retries within
    a short window produce the **same** key — the upstream uses the key
    to de-duplicate, so we want every retry of "the same user intent" to
    carry the same key, even though it's a fresh HTTP request.

    Args:
        user_id: Stable user identifier (e.g. subject claim, not session id).
        body: JSON-serialisable request body.
        timestamp: Unix seconds; defaults to ``time.time()``. Tests inject
            a fixed value to exercise bucket-boundary behaviour.
    """

    ts = time.time() if timestamp is None else timestamp
    bucket = int(ts) // 300
    raw = f"{user_id}{_body_hash(body)}{bucket}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _extract_user_id_and_body(args: tuple, kwargs: dict) -> tuple[str, Any]:
    """Pick (user_id, body) out of the wrapped call's positional/kwarg args.

    Convention: the wrapped async callable is called with
    ``func(user_id, body, ...)`` (user_id first, body second). Keyword
    overrides win so tests can force the key source explicitly.
    """

    user_id: Any = kwargs.get("_retry_user_id")
    if user_id is None and args:
        user_id = args[0]
    body: Any = kwargs.get("_retry_body")
    if body is None:
        body = kwargs.get("body", args[1] if len(args) > 1 else {})
    return (str(user_id) if user_id is not None else "", body)


class RetryWithIdempotency:
    """Decorator that adds HA failover retry with idempotency key to an async callable.

    Usage::

        @RetryWithIdempotency(max_retries=3, window_seconds=5)
        async def call_gateway(user_id, body, headers):
            headers = {**headers, "Idempotency-Key": idempotency_key_for(body)}
            return await client.post(..., headers=headers)

    The decorator:

    1. Computes ``Idempotency-Key`` from the first positional ``user_id``
       and second positional ``body`` argument on every invocation
       (5-minute bucket makes the key stable across retries).
    2. Injects the key as the ``idempotency_key`` keyword argument on
       every call to the wrapped function. Callers forward it as the
       ``Idempotency-Key`` HTTP header to the upstream.
    3. On ``HAFailoverError(status_code=503)`` or ``ConnectionError``,
       retries within the time window up to ``max_retries`` times.
    4. On any other exception (including non-503 ``HAFailoverError``,
       ``ValueError``, etc.), propagates immediately without retry.
    """

    def __init__(self, max_retries: int = 3, window_seconds: float = 5.0) -> None:
        if max_retries < 1:
            raise ValueError("max_retries must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self.max_retries = max_retries
        self.window_seconds = float(window_seconds)

    def __call__(
        self, func: Callable[..., Awaitable[Any]]
    ) -> Callable[..., Awaitable[Any]]:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            user_id, body = _extract_user_id_and_body(args, kwargs)

            attempt = 0
            last_error: Exception | None = None
            while attempt < self.max_retries:
                attempt += 1
                # Recompute the key each attempt so a retry that crosses
                # a 5-minute bucket boundary picks up the new bucket.
                idempotency_key = compute_idempotency_key(user_id, body)
                try:
                    return await func(*args, idempotency_key=idempotency_key, **kwargs)
                except HAFailoverError as exc:
                    # Only 503 is the HA failover signal. Any other 5xx
                    # (500/502/504) is owned by the upstream's own 1-shot
                    # retry — we MUST NOT stack a second retry layer.
                    if exc.status_code != 503:
                        raise
                    last_error = exc
                except ConnectionError as exc:
                    # Transport-level glitch during instance drain. Treat
                    # as retryable per spec ("503 HA_FAILOVER 状态码或
                    # 连接被中断").
                    last_error = exc

                if attempt < self.max_retries:
                    # Sleep proportionally to remaining budget — early
                    # failures get more headroom than late ones.
                    remaining = self.window_seconds / max(1, self.max_retries - 1)
                    await asyncio.sleep(min(remaining, self.window_seconds))

            # All attempts exhausted.
            raise HAFailoverExhausted(
                f"HA failover exhausted after {attempt} attempts: {last_error}",
                attempts=attempt,
            )

        return wrapper


__all__ = [
    "HAFailoverError",
    "HAFailoverExhausted",
    "RetryWithIdempotency",
    "compute_idempotency_key",
]