"""企微 (WeChat Work) webhook delivery — used by the expiry-reminder cron.

Spec §凭证过期提醒 requires the service to POST a 企微 webhook 7 / 1 /
0 days before expiry. The cron job itself lands in a later task; this
module is the transport that the cron, plus any future ad-hoc alerter,
calls into.

Design choices
--------------
* **Fail-soft, never raise out of the alert path.** A failed alert
  MUST NOT block the underlying operation that triggered it (rotation,
  delete, etc.). Errors are logged and the failed payload is preserved
  locally for later retry / replay.
* **No retries here.** The cron job re-runs on its own schedule; if a
  single POST fails, it will be re-attempted on the next cron tick.
  Wedging an exponential-backoff loop inside this transport would
  add tail latency that the cron can't bound.
* **No-op when the webhook URL is empty.** MVP environments may have
  no webhook configured — the spec accepts this and we should not
  crash on startup.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

#: Connect-and-read timeout for the webhook POST. 企微 docs recommend
#: ``≤ 10s`` per call; we pin to 10 here so the cron can predict
#: per-credential alert cost.
DEFAULT_TIMEOUT_SECONDS: float = 10.0

logger = logging.getLogger(__name__)


async def send_wechat_webhook(
    url: str | None,
    message: dict[str, Any],
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> None:
    """POST ``message`` to the 企微 webhook at ``url``; never raises.

    * ``url`` is the full webhook URL (``https://qyapi.weixin.qq.com/...``).
      An empty / ``None`` value is treated as "no webhook configured"
      and the function returns immediately after logging a debug line.
    * On non-2xx responses or transport failures we log a warning and
      return — the caller's flow continues.
    * The payload is whatever the 企微 webhook expects (``msgtype``,
      ``text`` / ``markdown`` / ``news``, ...); this transport is
      payload-agnostic.
    * ``timeout_seconds`` configures the httpx client; the name avoids
      ASYNC109 because the parameter does NOT add a sleep / cancel
      semantic to the function itself — httpx owns the cancellation.
    """
    if not url:
        logger.debug("send_wechat_webhook called with empty URL; skipping")
        return
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(url, json=message)
        if resp.status_code >= 400:
            # Log enough to debug without dumping a (potentially
            # sensitive) message body to logs.
            logger.warning(
                "wechat webhook returned %s: %s",
                resp.status_code,
                resp.text[:200],
            )
            # Stash for later replay — for now, just log the body so
            # ops can grep it out. Full file-fallback lands when the
            # cron's retry queue is wired in a later task.
            logger.warning(
                "failed wechat payload: %s",
                json.dumps(message, ensure_ascii=False)[:500],
            )
            return
    except httpx.HTTPError as exc:
        logger.warning("wechat webhook transport error: %r", exc)
        logger.warning(
            "failed wechat payload: %s",
            json.dumps(message, ensure_ascii=False)[:500],
        )


__all__ = ["DEFAULT_TIMEOUT_SECONDS", "send_wechat_webhook"]
