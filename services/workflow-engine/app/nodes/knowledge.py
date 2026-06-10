"""Knowledge retrieval node — query the knowledge-base service.

Calls the knowledge-base service's ``/retrieve`` endpoint via the stub client
in ``app/clients/knowledge_base.py``. The KB service ships in a later change
(``implement-knowledge-base``); the stub returns 503 until then, which the
client surfaces as ``WorkflowRuntimeError``.

The ``credential_id`` field is optional — KB nodes can be public (no
credential) or scoped to a user-managed KB. The workflow runner enforces
the access check at workflow start time, not here.
"""
from __future__ import annotations

from pydantic import Field

from app.clients.knowledge_base import KnowledgeBaseClient
from app.graph.jinja import render_jinja
from app.nodes.contracts.base import BaseConfig, BaseNode
from app.nodes.registry import register


class KnowledgeConfig(BaseConfig):
    """Configuration for the knowledge retrieval node."""

    knowledge_base_id: str = Field(..., description="知识库 ID")
    query: str = Field(..., description="Jinja2 检索 query 模板,渲染后作为检索输入")
    top_k: int = Field(5, ge=1, le=100)
    credential_id: str = Field(
        "",
        description="(optional) 凭证 ID;空字符串表示公开知识库,workflow runner 会跳过访问校验",
    )


@register("knowledge", version="1.0.0")
class KnowledgeNode(BaseNode):
    """Node contract for the knowledge retrieval node."""

    config: KnowledgeConfig


async def knowledge_execute(config: KnowledgeConfig, inputs: dict) -> dict:
    """Render the query template, hit the KB retrieve endpoint, return the parsed body.

    The KB service's response schema is documented in the
    ``implement-knowledge-base`` change; until it lands, the stub returns 503
    and the client raises ``WorkflowRuntimeError``.
    """
    rendered_query = render_jinja(config.query, inputs)
    client = KnowledgeBaseClient()
    try:
        resp = await client.retrieve(config.knowledge_base_id, rendered_query, config.top_k)
        return resp
    finally:
        await client.aclose()


__all__ = ["KnowledgeConfig", "KnowledgeNode", "knowledge_execute"]
