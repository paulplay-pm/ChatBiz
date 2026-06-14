"""Unit tests for ``RetryWithIdempotency`` (task 3.1 of gateway-egress-enforcement-p0).

Per spec 3.1:
  * ``Idempotency-Key`` = SHA-256(user_id + body_hash + 5min timestamp bucket)
  * On ``503 HA_FAILOVER`` or connection interruption, retry up to 3 times
    within a 5s wall-clock window
  * Existing 5xx upstream retry in ``call_upstream`` stays unchanged
    (the two retry layers compose)

Strategy: mock the wrapped callable directly so we don't need a real
upstream. Each test sets up a sequence of responses (e.g.
[503_ha_failover, 503_ha_failover, 200]) and verifies the decorator
calls the wrapped function the right number of times, with the
right Idempotency-Key on each call, and returns the right thing.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.llm import client as client_mod
from app.llm.client import (
    BACKOFFS_S,
    BUCKET_SECONDS,
    CONNECTION_INTERRUPTED_EXCEPTIONS,
    MAX_ATTEMPTS,
    MAX_TOTAL_SECONDS,
    call_upstream_with_idempotency,
    compute_idempotency_key,
    retry_with_idempotency,
)


def _run(coro):
    """Tiny helper: run an async coroutine to completion in a fresh loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mk_response(status: int, body: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        json=body or {"ok": True},
        request=httpx.Request("POST", "http://example.com/v1/chat/completions"),
    )


def _ha_failover_resp() -> httpx.Response:
    return _mk_response(503, {"error": "HA_FAILOVER"})


def _ok_resp() -> httpx.Response:
    return _mk_response(200, {"choices": [{"text": "hi"}]})


# ---------- compute_idempotency_key ---------------------------------------

def test_idempotency_key_is_64_hex_chars() -> None:
    """SHA-256 hex digest is exactly 64 hex characters."""
    key = compute_idempotency_key("user-1", {"prompt": "hi"}, now=1_700_000_000.0)
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_idempotency_key_stable_within_5min_bucket() -> None:
    """Two calls in the same 5-minute bucket produce the same key."""
    # 1_700_000_100.0 is a multiple of 300, so we're at the start of
    # bucket 5666667. Adding up to 4 minutes keeps us in the same bucket.
    base = 1_700_000_100.0
    key1 = compute_idempotency_key("user-1", {"x": 1}, now=base)
    key2 = compute_idempotency_key("user-1", {"x": 1}, now=base + 4 * 60)
    assert key1 == key2, "same user+body within 5min should hash to same key"


def test_idempotency_key_changes_across_bucket_boundary() -> None:
    """Two calls spanning a bucket boundary produce different keys."""
    base = 1_700_000_100.0
    key1 = compute_idempotency_key("user-1", {"x": 1}, now=base)
    key2 = compute_idempotency_key("user-1", {"x": 1}, now=base + 5 * 60 + 1)  # 5 min + 1s
    assert key1 != key2, "calls spanning a 5min bucket boundary must produce different keys"


def test_idempotency_key_changes_with_user_id() -> None:
    key1 = compute_idempotency_key("user-A", {"x": 1}, now=1_700_000_000.0)
    key2 = compute_idempotency_key("user-B", {"x": 1}, now=1_700_000_000.0)
    assert key1 != key2


def test_idempotency_key_changes_with_body() -> None:
    key1 = compute_idempotency_key("user-1", {"x": 1}, now=1_700_000_000.0)
    key2 = compute_idempotency_key("user-1", {"x": 2}, now=1_700_000_000.0)
    assert key1 != key2


# ---------- retry_with_idempotency: success path -------------------------

def test_first_attempt_success_returns_immediately() -> None:
    """If the first attempt returns 200, the wrapped function is called once."""
    wrapped = AsyncMock(return_value=_ok_resp())
    decorated = retry_with_idempotency(wrapped)

    resp = _run(decorated("http://x", "/v1/chat", {"prompt": "hi"}, {"X-User-Id": "u1"}))

    assert resp.status_code == 200
    assert wrapped.call_count == 1


def test_successful_attempt_includes_idempotency_key() -> None:
    """The Idempotency-Key header must be present on every attempt."""
    wrapped = AsyncMock(return_value=_ok_resp())
    decorated = retry_with_idempotency(wrapped)

    _run(decorated("http://x", "/v1/chat", {"prompt": "hi"}, {"X-User-Id": "u1"}))

    call = wrapped.call_args
    headers = call.kwargs.get("headers") or call.args[3]
    assert "Idempotency-Key" in headers, f"Idempotency-Key not in headers: {headers}"
    assert len(headers["Idempotency-Key"]) == 64


def test_caller_headers_not_mutated() -> None:
    """The decorator must not pollute the caller's headers dict."""
    wrapped = AsyncMock(return_value=_ok_resp())
    decorated = retry_with_idempotency(wrapped)
    caller_headers = {"X-User-Id": "u1"}

    _run(decorated("http://x", "/v1/chat", {"prompt": "hi"}, caller_headers))

    assert "Idempotency-Key" not in caller_headers, (
        f"caller's headers were mutated: {caller_headers}"
    )


# ---------- retry_with_idempotency: HA failover 503 -----------------------

def test_retries_on_ha_failover_503_then_succeeds() -> None:
    """Spec literal: 2 fail then succeed on attempt 3.

    Setup: wrapped returns [503_HA_FAILOVER, 503_HA_FAILOVER, 200].
    Expectation: decorator calls wrapped 3 times, returns the 200.
    """
    wrapped = AsyncMock(side_effect=[
        _ha_failover_resp(),
        _ha_failover_resp(),
        _ok_resp(),
    ])
    decorated = retry_with_idempotency(wrapped)

    resp = _run(decorated("http://x", "/v1/chat", {"prompt": "hi"}, {"X-User-Id": "u1"}))

    assert resp.status_code == 200
    assert wrapped.call_count == 3


def test_returns_last_ha_failover_after_max_attempts() -> None:
    """If all 3 attempts return 503 HA_FAILOVER, decorator returns the last 503
    (does not raise). The caller can then map it to a 5xx response."""
    wrapped = AsyncMock(side_effect=[
        _ha_failover_resp(),
        _ha_failover_resp(),
        _ha_failover_resp(),
    ])
    decorated = retry_with_idempotency(wrapped)

    resp = _run(decorated("http://x", "/v1/chat", {"prompt": "hi"}, {"X-User-Id": "u1"}))

    assert resp.status_code == 503
    assert wrapped.call_count == MAX_ATTEMPTS == 3


def test_503_without_ha_failover_marker_is_not_retried() -> None:
    """A plain 503 (no HA_FAILOVER body) is NOT a retry signal — return it.

    Reason: an upstream 503 with a different body (e.g. rate limit
    message) is semantically different from HA failover. The inner
    call_upstream retry already covers generic 5xx; the outer
    decorator only fires on the HA failover signal.
    """
    plain_503 = _mk_response(503, {"error": "rate_limited"})
    wrapped = AsyncMock(return_value=plain_503)
    decorated = retry_with_idempotency(wrapped)

    resp = _run(decorated("http://x", "/v1/chat", {"prompt": "hi"}, {"X-User-Id": "u1"}))

    assert resp.status_code == 503
    assert wrapped.call_count == 1, "plain 503 should not be retried by outer decorator"


# ---------- retry_with_idempotency: connection interrupted ----------------

def test_retries_on_connect_error() -> None:
    """ConnectionError (httpx.ConnectError) is in CONNECTION_INTERRUPTED_EXCEPTIONS."""
    wrapped = AsyncMock(side_effect=[
        httpx.ConnectError("connection refused"),
        _ok_resp(),
    ])
    decorated = retry_with_idempotency(wrapped)

    resp = _run(decorated("http://x", "/v1/chat", {"prompt": "hi"}, {"X-User-Id": "u1"}))

    assert resp.status_code == 200
    assert wrapped.call_count == 2


def test_raises_last_connection_error_after_max_attempts() -> None:
    """If all 3 attempts raise ConnectError, the LAST exception is re-raised."""
    last_err = httpx.ConnectError("persistent failure")
    wrapped = AsyncMock(side_effect=[
        httpx.ConnectError("first"),
        httpx.ConnectError("second"),
        last_err,
    ])
    decorated = retry_with_idempotency(wrapped)

    with pytest.raises(httpx.ConnectError) as exc_info:
        _run(decorated("http://x", "/v1/chat", {"prompt": "hi"}, {"X-User-Id": "u1"}))

    assert exc_info.value is last_err
    assert wrapped.call_count == 3


# ---------- retry_with_idempotency: idempotency key stability across attempts

def test_idempotency_key_is_same_across_retries() -> None:
    """All retry attempts must use the same Idempotency-Key (same 5min bucket).

    This is what tells the upstream "these are the same request being
    retried" rather than "three different requests".
    """
    wrapped = AsyncMock(side_effect=[
        _ha_failover_resp(),
        _ha_failover_resp(),
        _ok_resp(),
    ])
    decorated = retry_with_idempotency(wrapped)

    _run(decorated("http://x", "/v1/chat", {"prompt": "hi"}, {"X-User-Id": "u1"}))

    keys = [
        (call.kwargs.get("headers") or call.args[3])["Idempotency-Key"]
        for call in wrapped.call_args_list
    ]
    assert len(set(keys)) == 1, f"keys differ across attempts: {keys}"


# ---------- retry_with_idempotency: time budget ---------------------------

def test_wall_clock_budget_stops_retrying() -> None:
    """If elapsed time is past MAX_TOTAL_SECONDS after a failed attempt,
    the decorator should stop calling the wrapped function (no more
    retries even if attempts remain).

    We patch time.monotonic to report a value past the budget from the
    start, and asyncio.sleep to a no-op, so the test runs in <1s.
    """
    side_effects = [
        _ha_failover_resp(),
        _ha_failover_resp(),
        _ok_resp(),  # never reached
    ]

    real_start = [time.monotonic()]
    elapsed_holder = [0.0]
    call_log: list[str] = []

    async def fake_call(*args, **kwargs):
        # Bump elapsed past the budget after each call.
        elapsed_holder[0] = MAX_TOTAL_SECONDS + 0.1
        result = side_effects[len(call_log)]
        call_log.append("called")
        # If side_effects is a Response (not coroutine), just return it
        return result

    wrapped = fake_call
    decorated = retry_with_idempotency(wrapped)

    def monotonic_with_budget():
        return real_start[0] + elapsed_holder[0]

    with (
        patch("app.llm.client.time.monotonic", side_effect=monotonic_with_budget),
        patch("app.llm.client.asyncio.sleep", new=AsyncMock()),
    ):
        resp = _run(decorated("http://x", "/v1/chat", {"prompt": "hi"}, {"X-User-Id": "u1"}))

    assert len(call_log) == 1, (
        f"expected 1 call (budget trip after attempt 0), got {len(call_log)}"
    )
    assert resp.status_code == 503


def test_backoffs_total_under_wall_clock_budget() -> None:
    """The 3 backoffs (200ms + 400ms + 800ms = 1.4s) must fit in the
    5s wall-clock budget, leaving room for actual upstream call time.
    This is a regression guard against accidentally increasing backoffs."""
    assert sum(BACKOFFS_S) < MAX_TOTAL_SECONDS, (
        f"backoffs sum {sum(BACKOFFS_S)}s must be < {MAX_TOTAL_SECONDS}s budget"
    )


# ---------- call_upstream_with_idempotency (decorated entry point) -------

def test_call_upstream_with_idempotency_is_decorated() -> None:
    """The exported call_upstream_with_idempotency function must be wrapped
    by retry_with_idempotency — i.e. its __wrapped__ attribute exists.
    This guards against accidental removal of the decorator."""
    assert hasattr(call_upstream_with_idempotency, "__wrapped__"), (
        "call_upstream_with_idempotency must be the retry_with_idempotency-decorated "
        "version of call_upstream, not the bare function"
    )


def test_call_upstream_with_idempotency_retries_on_ha_failover() -> None:
    """End-to-end: 2 HA_FAILOVER 503s then success, with the bare
    call_upstream mocked to return the canned sequence. Decorator must
    see the failover, retry, and surface the success."""
    from app.llm import client as client_mod_real

    bare = AsyncMock(side_effect=[
        _ha_failover_resp(),
        _ha_failover_resp(),
        _ok_resp(),
    ])

    # Patch call_upstream at the module level so the decorated entry
    # point sees the mock. Use wraps to keep the call signature
    # inspection working.
    with patch.object(client_mod_real, "call_upstream", side_effect=bare):
        # Pass headers as kwarg only (not positional) so the decorator
        # doesn't see them as both positional and keyword.
        resp = _run(call_upstream_with_idempotency(
            base_url="http://x",
            path="/v1/chat",
            body={"prompt": "hi"},
            headers={"X-User-Id": "u1"},
        ))

    assert resp.status_code == 200
    assert bare.call_count == 3


# ---------- connection-interrupted exception list sanity ------------------

def test_connection_interrupted_excludes_unrelated_exceptions() -> None:
    """Sanity: the tuple must NOT include generic HTTPException, ValueError,
    or other non-connection errors. Including them would cause spurious
    retries on every 4xx upstream error."""
    from app.llm import client as _c
    assert httpx.HTTPError not in _c.CONNECTION_INTERRUPTED_EXCEPTIONS
    assert ValueError not in _c.CONNECTION_INTERRUPTED_EXCEPTIONS
    assert KeyError not in _c.CONNECTION_INTERRUPTED_EXCEPTIONS


def test_connection_interrupted_includes_core_transport_exceptions() -> None:
    assert httpx.ConnectError in CONNECTION_INTERRUPTED_EXCEPTIONS
    assert httpx.RemoteProtocolError in CONNECTION_INTERRUPTED_EXCEPTIONS
    assert httpx.ReadTimeout in CONNECTION_INTERRUPTED_EXCEPTIONS


# ---------- module-level constants ----------------------------------------

def test_max_attempts_is_3() -> None:
    """Spec literal: 最多 3 次 (max 3 attempts)."""
    assert MAX_ATTEMPTS == 3


def test_max_total_seconds_is_5() -> None:
    """Spec literal: 5s 内 (within 5 seconds)."""
    assert MAX_TOTAL_SECONDS == 5.0


def test_bucket_seconds_is_5_minutes() -> None:
    """Spec: 5min timestamp bucket."""
    assert BUCKET_SECONDS == 5 * 60
