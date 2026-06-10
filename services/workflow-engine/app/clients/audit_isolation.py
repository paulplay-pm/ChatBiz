"""Client for the audit-and-isolation gateway.

The workflow engine does **not** call LLM providers directly — every
chat completion goes through the audit-and-isolation gateway's
``/v1/chat/completions`` endpoint so that:

* PII redaction is enforced at the egress point (see
  ``docs/architecture.md`` §4 数据隔离网关 — 2 instance HA + health
  check + cross-gateway trace-id correlation).
* The audit log captures every model invocation with full request
  body, response body, and trace correlation.
* The gateway's retry/rate-limit/credential-injection layers are
  applied uniformly.

The client is a thin ``httpx`` wrapper — no retry logic here, the
gateway already handles 5xx + transport retries (see
``services/audit-and-isolation/app/llm/client.py``). On a 5xx the
gateway returns the error response to us and we propagate it up
through ``raise_for_status()``.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings


class AuditIsolationClient:
    """Client for audit-and-isolation OpenAI-compatible ``/v1/chat/completions`` endpoint."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            s = get_settings()
            self._client = httpx.AsyncClient(
                base_url=s.audit_isolation_url,
                timeout=httpx.Timeout(30.0, connect=5.0),
                headers={
                    "X-Service-Token": s.workflow_engine_service_token,
                    "X-Trace-Id": "wf-trace",
                },
            )
        return self._client

    async def chat(self, model: str, messages: list[dict], **kwargs) -> dict[str, Any]:
        """POST to ``/v1/chat/completions`` and return the parsed JSON body."""
        c = await self._get_client()
        r = await c.post(
            "/v1/chat/completions",
            json={"model": model, "messages": messages, **kwargs},
        )
        r.raise_for_status()
        return r.json()

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


__all__ = ["AuditIsolationClient"]
