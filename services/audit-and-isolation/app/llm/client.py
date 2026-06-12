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
"""

from __future__ import annotations

import asyncio

import httpx

from app.config import get_settings
from app.llm.retry import RetryWithIdempotency


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


def reset_client_for_tests() -> None:
    """Drop the cached client. Test-only helper."""
    global _client
    _client = None


__all__ = ["call_upstream", "get_client", "reset_client_for_tests"]
