"""Stub client for the knowledge-base service.

The knowledge-base service ships in a later change
(``implement-knowledge-base``). Until it lands, this client surfaces
a clear ``WorkflowRuntimeError`` on 503 so callers know to either
skip knowledge-base nodes or block the workflow from being saved.

The URL is still configured (``knowledge_base_url`` in
``app/config.py``) so the workflow engine can boot and the
knowledge-base can be wired up as soon as it's deployed — no config
change required.

When the knowledge-base service is implemented, this client should
keep the same surface (``retrieve``) so node executors don't have to
change.
"""

from __future__ import annotations

import httpx

from app.config import get_settings
from app.errors.classes import WorkflowRuntimeError


class KnowledgeBaseClient:
    """Stub client for knowledge-base service (not yet implemented).

    Returns 503 until ``implement-knowledge-base`` lands.
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            s = get_settings()
            self._client = httpx.AsyncClient(
                base_url=s.knowledge_base_url,
                timeout=httpx.Timeout(10.0, connect=3.0),
            )
        return self._client

    async def retrieve(self, knowledge_base_id: str, query: str, top_k: int = 5) -> dict:
        """POST to ``/retrieve`` and return the parsed JSON body.

        Raises ``WorkflowRuntimeError`` (our custom class) on 503 so
        callers see a clear "service not yet implemented" message
        rather than a raw httpx error.
        """
        c = await self._get_client()
        try:
            r = await c.post(
                "/retrieve",
                json={
                    "knowledge_base_id": knowledge_base_id,
                    "query": query,
                    "top_k": top_k,
                },
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                raise WorkflowRuntimeError(
                    "knowledge-base service 未实现,请在 implement-knowledge-base change 落地后接入"
                ) from e
            raise

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


__all__ = ["KnowledgeBaseClient"]
