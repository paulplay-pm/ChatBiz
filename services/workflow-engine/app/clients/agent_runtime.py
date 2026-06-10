"""Stub client for the agent-runtime service.

The agent-runtime service ships in a later change
(``implement-agent-runtime``). Until it lands, this client surfaces
a clear ``WorkflowRuntimeError`` on 503 so callers know the runtime
is not yet wired up.

The URL is still configured (``agent_runtime_url`` in
``app/config.py``) so the workflow engine can boot and the
agent-runtime can be wired up as soon as it's deployed — no config
change required.
"""

from __future__ import annotations

import httpx

from app.config import get_settings
from app.errors.classes import WorkflowRuntimeError


class AgentRuntimeClient:
    """Stub client for agent-runtime service (not yet implemented)."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            s = get_settings()
            self._client = httpx.AsyncClient(
                base_url=s.agent_runtime_url,
                timeout=httpx.Timeout(30.0, connect=5.0),
            )
        return self._client

    async def invoke(self, agent_id: str, task: str, **kwargs) -> dict:
        """POST to ``/invoke`` and return the parsed JSON body.

        Raises ``WorkflowRuntimeError`` (our custom class) on 503 so
        callers see a clear "service not yet implemented" message.
        """
        c = await self._get_client()
        try:
            r = await c.post(
                "/invoke",
                json={"agent_id": agent_id, "task": task, **kwargs},
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                raise WorkflowRuntimeError(
                    "agent-runtime service 未实现,请在 implement-agent-runtime change 落地后接入"
                ) from e
            raise

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


__all__ = ["AgentRuntimeClient"]
