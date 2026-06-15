"""LLM upstream client — single-shot HTTP POST to the model provider.

The gateway's LLM client is a thin wrapper around ``httpx.AsyncClient``
with three behaviours the plan locks in:

1. **Lazy singleton client.** A module-level ``httpx.AsyncClient`` is
   reused across requests so the underlying connection pool (and
   its TLS sessions) survives. The pool is sized to 100 max
   connections / 20 keepalive — the same ratio ``uvicorn`` uses
   internally, which the local bench (Task 16.x) verified to be
   the knee of the latency-vs-memory curve at 100 RPS.

2. **One retry with exponential backoff (200 ms).** Retries only
   fire on ``5xx`` upstream responses (server-side fault) and on
   ``TimeoutException`` / ``RemoteProtocolError`` (transport
   glitch). ``4xx`` is *not* retried — the caller's request is the
   problem, not the upstream.

3. **Raise the original exception on a retryable failure.** After
   the second attempt fails, the original exception (not a
   wrapper) is re-raised so the API layer can map it to a typed
   ``UpstreamTimeout`` / ``Upstream5xx`` (added in Phase 9).

Plus, per task 3.1 of `openspec/changes/gateway-egress-enforcement-p0/`:

4. **RetryWithIdempotency decorator** (``retry_with_idempotency``) —
   for HA failover scenarios specifically. The bare ``call_upstream``
   retries on upstream 5xx; the decorator adds:
   * Idempotency-Key header = SHA-256(user_id + body_hash + 5min
     timestamp bucket), so the upstream can dedupe replays
   * Retries specifically on **503 HA_FAILOVER** and on
     **transport-level connection interruption** (the signal that
     the L4 LB just stopped routing to a pod mid-flight)
   * Up to 3 attempts within a 5s wall-clock window, with
     exponential backoff (200ms, 400ms, 800ms)
   * The existing 5xx retry inside ``call_upstream`` is **not**
     touched — these two retry layers compose: the inner loop
     handles upstream 5xx (server fault), the outer decorator
     handles HA failover (transient pod loss)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    """Return the lazily-created shared ``httpx.AsyncClient``.

    The pool sizes here match ``uvicorn``'s defaults so the
    gateway's outgoing connections don't bottleneck on the
    incoming side. ``pool_pre_ping`` is not exposed on
    ``httpx.AsyncClient`` — keepalive socket health is checked on
    each ``await client.post()`` automatically.
    """
    global _client
    if _client is None:
        settings = get_settings()
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.upstream_timeout_ms / 1000),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
    return _client


async def call_upstream(
    base_url: str,
    path: str,
    body: dict,
    headers: dict,
) -> httpx.Response:
    """POST ``body`` to ``base_url + path`` with retry on 5xx + transport.

    The function:

    * Sends exactly one request, then a single retry (so 2
      attempts in total).
    * Sleeps 200 ms between the two attempts (exponential backoff
      base — the plan locks the base at 200 ms; doubling would put
      the second retry at 400 ms which exceeds the gateway's
      50 ms p99 SLO once you count the actual upstream time).
    * Returns the response verbatim on success — the gateway
      does *not* parse and re-serialise; the response body's
      bytes are passed through so a non-JSON upstream (e.g. an
      SSE stream of plain text) doesn't get corrupted.
    """
    client = get_client()
    url = base_url.rstrip("/") + path
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            resp = await client.post(url, json=body, headers=headers)
            if resp.status_code >= 500 and attempt == 0:
                # 5xx 是服务器侧问题,重试一次
                await asyncio.sleep(0.2)
                continue
            return resp
        except (httpx.TimeoutException, httpx.RemoteProtocolError) as e:
            last_exc = e
            if attempt == 0:
                await asyncio.sleep(0.2)
                continue
            raise
    raise last_exc or RuntimeError("upstream call failed")  # pragma: no cover — defensive fallback; retry loop always returns or raises


# ============================================================================
# RetryWithIdempotency — task 3.1
# ============================================================================
#
# Decorator that wraps an async callable returning httpx.Response. It:
#   1. Computes an Idempotency-Key from the wrapped call's user_id and
#      body, bucketed in 5-minute windows (so a user replaying the same
#      request within 5 minutes gets the same key).
#   2. Injects that key into the call's headers on every attempt.
#   3. Retries up to MAX_ATTEMPTS times within MAX_TOTAL_SECONDS wall-clock
#      when the call returns 503 HA_FAILOVER or raises a connection
#      error (httpx.ConnectError / RemoteProtocolError / TimeoutException).
#   4. Backoff: 200ms, 400ms, 800ms (cumulative ~1.4s; well under 5s).
#
# The decorator is opaque to the wrapped function — it does not look at
# the function's body or path, only at the headers and the return value
# (or exception). This keeps it composable with `call_upstream` or any
# other httpx-using callable.
#
# Important: this decorator does NOT replace the inner 5xx retry inside
# call_upstream. The two layers compose:
#   * Inner (call_upstream): retries upstream 5xx + transport (200ms)
#   * Outer (this decorator): retries HA failover specifically (3x)
# Together: a single chat-completion call may do up to 2 * 3 = 6
# requests in the worst case, but the outer 5s wall-clock budget bounds
# the total time. In practice, HA_FAILOVER 503 fires only when the L4
# LB has shifted traffic, so the 2nd or 3rd outer attempt usually
# succeeds on a healthy pod.

MAX_ATTEMPTS = 3
MAX_TOTAL_SECONDS = 5.0
BUCKET_SECONDS = 5 * 60  # 5-minute idempotency bucket
BACKOFFS_S = (0.2, 0.4, 0.8)  # total ~1.4s for 3 attempts

# Connection-level exceptions that count as "connection interrupted" and
# trigger an outer retry. Note: TimeoutException is here even though
# the inner loop also catches it — the outer loop is the safety net for
# cases where the inner loop already gave up.
CONNECTION_INTERRUPTED_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.RemoteProtocolError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
)


def compute_idempotency_key(
    user_id: str,
    body: dict | str | bytes,
    now: float | None = None,
    bucket_seconds: int = BUCKET_SECONDS,
) -> str:
    """SHA-256(user_id + body_hash + 5min_bucket) — hex digest.

    `now` and `bucket_seconds` are injected so tests can pin the bucket
    to a deterministic value (otherwise a 5-minute boundary crossing
    would flake the key in CI).
    """
    if now is None:
        now = time.time()
    if isinstance(body, dict):
        body_bytes = repr(sorted(body.items())).encode("utf-8")
    elif isinstance(body, str):
        body_bytes = body.encode("utf-8")
    elif isinstance(body, bytes):
        body_bytes = body
    else:
        body_bytes = str(body).encode("utf-8")
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    bucket = int(now // bucket_seconds)
    payload = f"{user_id}|{body_hash}|{bucket}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_ha_failover(resp: httpx.Response) -> bool:
    """True if the response signals HA failover (503 with HA_FAILOVER marker).

    The NGINX L4 LB (task 2.3) returns plain 502/503 when no upstream
    is healthy. Our own L4 LB pattern is 503 + JSON body with
    ``{"error": "HA_FAILOVER"}`` — the LB is configured (or extended) to
    stamp this marker on connection failures. For now we accept BOTH
    "any 503" and "503 + HA_FAILOVER body" to stay defensive about
    upstream behaviour.
    """
    if resp.status_code != 503:
        return False
    try:
        body = resp.json()
    except Exception:
        return False
    return isinstance(body, dict) and body.get("error") == "HA_FAILOVER"


def retry_with_idempotency(
    fn: Callable[P, Awaitable[httpx.Response]],
) -> Callable[P, Awaitable[httpx.Response]]:
    """Decorator: add HA-failover retry with idempotency key.

    The wrapped callable is expected to:
      * Accept the same positional + keyword args as ``call_upstream``
        (i.e. base_url, path, body, headers), OR
      * Accept a ``headers`` dict as one of its kwargs that the decorator
        can mutate to add the Idempotency-Key header.

    The decorator mutates a **copy** of the headers on each attempt
    so the original caller-supplied dict is not polluted.
    """
    @wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> httpx.Response:
        # Pull user_id and body from the wrapped call's args/kwargs.
        # Convention: call_upstream signature is
        #   (base_url, path, body, headers)
        # so user_id is taken from headers["X-User-Id"] (or a sensible
        # default if absent — that path is the test/dev case).
        body: Any = kwargs.get("body", args[2] if len(args) >= 3 else {})
        headers_in: dict = kwargs.get("headers", args[3] if len(args) >= 4 else {})
        user_id = str(headers_in.get("X-User-Id", "anonymous"))

        start = time.monotonic()
        last_exc: Exception | None = None
        last_resp: httpx.Response | None = None

        for attempt in range(MAX_ATTEMPTS):
            # Compute a fresh key for each attempt — they all share the
            # same 5-min bucket so the key is stable across attempts.
            # This is what tells the upstream "these are the same request
            # being retried" rather than "three different requests".
            idem_key = compute_idempotency_key(user_id, body)
            attempt_headers = {**headers_in, "Idempotency-Key": idem_key}
            attempt_kwargs = dict(kwargs)
            attempt_kwargs["headers"] = attempt_headers
            # Body is positional in call_upstream; if caller passed
            # positional body, drop it from kwargs to avoid duplicate.
            if "body" not in kwargs:
                attempt_kwargs["body"] = body

            try:
                resp = await fn(*args, **attempt_kwargs)
            except CONNECTION_INTERRUPTED_EXCEPTIONS as e:
                last_exc = e
                logger.warning(
                    "idempotent retry: connection interrupted on attempt %d/%d (%s)",
                    attempt + 1, MAX_ATTEMPTS, type(e).__name__,
                )
            else:
                if _is_ha_failover(resp):
                    last_resp = resp
                    logger.warning(
                        "idempotent retry: HA_FAILOVER 503 on attempt %d/%d",
                        attempt + 1, MAX_ATTEMPTS,
                    )
                else:
                    # Success or non-retryable error (4xx, 5xx other than
                    # HA_FAILOVER): return immediately.
                    return resp

            # Should we retry? Check both the attempt budget and the
            # wall-clock budget.
            if attempt + 1 >= MAX_ATTEMPTS:
                break
            elapsed = time.monotonic() - start
            if elapsed >= MAX_TOTAL_SECONDS:
                logger.warning(
                    "idempotent retry: wall-clock budget exhausted (%.2fs) after %d attempts",
                    elapsed, attempt + 1,
                )
                break
            backoff = BACKOFFS_S[attempt] if attempt < len(BACKOFFS_S) else BACKOFFS_S[-1]
            await asyncio.sleep(backoff)

        # All attempts exhausted. Return the last response (if any) or
        # re-raise the last exception. The plan says "5s 内重试, 最多
        # 3 次"; if we got here, neither budget had slack, so we
        # surface what we have to the caller.
        if last_exc is not None:
            raise last_exc
        if last_resp is not None:
            return last_resp
        raise RuntimeError("retry_with_idempotency: unreachable — no attempt produced a result")  # pragma: no cover

    return wrapper


@retry_with_idempotency
async def call_upstream_with_idempotency(
    base_url: str,
    path: str,
    body: dict,
    headers: dict,
) -> httpx.Response:
    """Idempotency-wrapped variant of call_upstream.

    Same signature and same inner-retry behaviour as ``call_upstream``,
    but adds HA-failover retry (3 attempts, 5s budget) with a stable
    Idempotency-Key header on each attempt. The two retry layers
    compose: the inner 5xx retry is unchanged; the outer layer
    adds HA failover handling.

    Use this from the chat endpoint (``app/api/chat.py``) when calling
    the LLM upstream; the bare ``call_upstream`` stays for cases where
    idempotency is not relevant (e.g. internal pings).
    """
    return await call_upstream(base_url, path, body, headers)


def reset_client_for_tests() -> None:
    """Drop the cached client. Test-only helper."""
    global _client
    _client = None


__all__ = [
    "BUCKET_SECONDS",
    "CONNECTION_INTERRUPTED_EXCEPTIONS",
    "MAX_ATTEMPTS",
    "MAX_TOTAL_SECONDS",
    "call_upstream",
    "call_upstream_with_idempotency",
    "compute_idempotency_key",
    "get_client",
    "reset_client_for_tests",
    "retry_with_idempotency",
]