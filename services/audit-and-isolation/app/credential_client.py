"""Credential client — fetch the LLM provider's API key per model.

The gateway does not embed any LLM provider key in its own config;
it asks the credential service for the right key for the requested
model. The key is cached in process memory for
``settings.credential_cache_ttl_seconds`` (default 5 min) so a burst
of requests for the same model doesn't flood the credential service.

Failure modes:

* **Credential service returns 503 on the first attempt** → retry
  once after a 200 ms backoff. The 5xx surface is a known
  deployment ordering issue (credential service rolling restart
  while the gateway is still up); a single retry almost always
  succeeds. If the second attempt also fails, the function
  propagates :class:`CredentialServiceUnavailable` to the caller,
  which the API layer maps to 503.
* **Network error** → treated the same as 503: one retry, then
  propagate.
* **Credential service returns non-200/non-503** → the function
  raises immediately; these are programmer errors (wrong model
  name, expired token, etc.) and are not transient.

Security:

* The ``service_token`` argument is read from the inbound
  ``Authorization`` header by the caller and **never** stored on
  this object. The cache key is the model name only; the token
  is forwarded on every upstream call. This way a token rotation
  on the credential service takes effect on the next call, with
  no cache to invalidate.
* The cached ``api_key`` value is held only in the process's
  in-memory dict; it is never logged, audited, or written to
  disk. (``CLAUDE.md`` "主密钥 / 凭证明文 MUST NOT 入 commit /
  log / audit".)
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# {model_name: (api_key, expire_at_unix_seconds)}
_cache: dict[str, tuple[str, float]] = {}


async def get_llm_api_key(model_name: str, token: str) -> str:
    """Return the LLM provider API key for ``model_name``.

    Caches the key in process memory for
    ``settings.credential_cache_ttl_seconds``. The ``token`` is
    the caller's service token (forwarded to the credential
    service for attribution); it is *not* cached.

    Raises :class:`CredentialServiceUnavailable` if the
    credential service is unreachable after the single retry.
    """
    now = time.time()
    if model_name in _cache:
        api_key, exp = _cache[model_name]
        if now < exp:
            return api_key

    settings = get_settings()
    async with httpx.AsyncClient(timeout=5.0) as client:
        for attempt in range(2):
            try:
                resp = await client.post(
                    f"{settings.credential_service_url}/v1/credentials/use",
                    json={"model_name": model_name, "service_token": token},
                )
                if resp.status_code == 200:
                    api_key = resp.json()["api_key"]
                    _cache[model_name] = (
                        api_key,
                        now + settings.credential_cache_ttl_seconds,
                    )
                    return api_key
                if resp.status_code == 503 and attempt == 0:
                    # 5xx 是部署瞬态问题,重试 1 次
                    await asyncio.sleep(0.2)
                    continue
                # 4xx 等非 200/5xx 错误,立即失败(不重试)
                raise RuntimeError(
                    f"credential service returned {resp.status_code}"
                )
            except httpx.HTTPError as e:
                if attempt == 0:
                    await asyncio.sleep(0.2)
                    continue
                logger.error(f"credential service unreachable: {e}")
                raise
    raise RuntimeError("credential service unavailable after retry")


def reset_cache_for_tests() -> None:
    """Drop the in-memory cache. Test-only helper."""
    global _cache
    _cache = {}


__all__ = ["get_llm_api_key", "reset_cache_for_tests"]
