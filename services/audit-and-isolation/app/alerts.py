"""Alert webhook dispatcher — fire a structured alert to the configured URL.

The audit-and-isolation service is the single egress point for all LLM
calls. When something goes wrong (PII detector fail-open, upstream 5xx,
credential service down, etc.) the on-call engineer needs a single,
correlated signal — not 20 different log lines to grep.

The webhook contract is intentionally minimal: a JSON POST with

    {
        "level":      "warning" | "critical",
        "error_class":"PiiFailOpen",
        "context":    {<k>: <v>, ...}
    }

The webhook URL is read from ``settings.alert_webhook_url``. In dev it
points at a no-op URL (``http://alerts:9090/alert``) — the call still
fires so the full code path is exercised, but the timeout (5 s) and
the swallow-on-error contract keep the gateway responsive even if the
webhook server is unreachable.

The "swallow on error" contract is the point: the gateway must never
let an alert-firing failure block the request that triggered the alert.
The user's request is the primary product; the alert is a *side effect*.
A retry loop on the alert side could block the chat response and is
explicitly out of scope (the dispatcher above is the alert side of
the 1/0 design). Operators rely on Prometheus counters + the chat
response log as the durable record.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def fire_alert(level: str, error_class: str, context: dict[str, Any]) -> None:
    """POST a structured alert to ``settings.alert_webhook_url``.

    Behaviour:

    * Timeout: 5 s (read + connect). The webhook is a side effect; a
      slow webhook MUST NOT slow the chat response.
    * Failure mode: any exception (network, timeout, 4xx, 5xx) is
      logged at WARNING and swallowed. The chat pipeline is never
      blocked by an alert failure.
    * Body: ``{"level": ..., "error_class": ..., "context": ...}``.
      The webhook server is expected to forward to a chat-ops channel
      (企微 / 钉钉 / Slack / PagerDuty) but the gateway has no opinion
      on the downstream.

    Parameters
    ----------
    level : str
        One of ``"info"``, ``"warning"``, ``"critical"``. Free-form;
        the webhook server validates against its own enum.
    error_class : str
        Short PascalCase tag, e.g. ``"PiiFailOpen"``,
        ``"Upstream5xx"``, ``"CredentialServiceDown"``.
    context : dict
        Free-form key/value pairs. The gateway emits
        ``{"trace_id": ..., "model": ..., "model_kind": ...}`` when
        those are available; the webhook server is the source of
        truth for which keys are required.
    """
    settings = get_settings()
    payload = {
        "level": level,
        "error_class": error_class,
        "context": context,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(settings.alert_webhook_url, json=payload)
    except Exception as e:
        # Swallow: alert failures MUST NOT block the request that
        # triggered them. Logged at warning so the on-call sees it
        # in logs (the prometheus counter is the durable record).
        logger.warning(
            f"alert webhook POST failed (level={level}, error_class={error_class}): {e}"
        )


__all__ = ["fire_alert"]
