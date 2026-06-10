"""LLM node — call a chat model via the audit-and-isolation gateway.

The workflow engine does **not** call LLM providers directly. Every chat
completion goes through the gateway's ``/v1/chat/completions`` so that:

* PII redaction is enforced at the egress point (data isolation gateway is
  the egress-enforcement node, see design doc finding #1).
* The audit log captures every model invocation with full request/response.
* The gateway's retry / rate-limit / credential-injection layers are applied
  uniformly.

The ``credential_id`` field is the *workflow-level* credential reference —
the workflow runner resolves it against the credential service at workflow
start time (not here, so a single 403 short-circuits the whole run rather
than 14 individual 403s for a 14-node workflow).
"""
from __future__ import annotations

from pydantic import Field

from app.clients.audit_isolation import AuditIsolationClient
from app.graph.jinja import render_jinja
from app.nodes.contracts.base import BaseConfig, BaseNode
from app.nodes.registry import register


class LLMConfig(BaseConfig):
    """Configuration for the LLM chat node."""

    model: str = Field(..., description="模型名, e.g. gpt-4 / qwen-max / claude-opus-4-8")
    credential_id: str = Field(
        ...,
        description="凭证 ID (workflow 启动时由 workflow runner 校验 user 访问权,见 credential service)",
    )
    prompt: str = Field(..., description="Jinja2 prompt 模板,渲染后作为 user message")
    system_prompt: str = Field("", description="(可选) system prompt 模板,渲染后作为 system message")
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, gt=0)


@register("llm", version="1.0.0")
class LLMNode(BaseNode):
    """Node contract for the LLM chat node."""

    config: LLMConfig


async def llm_execute(config: LLMConfig, inputs: dict) -> dict:
    """Render the prompt(s), call the gateway, return content + usage + raw response.

    The ``aclose()`` call is in a ``finally`` block so we don't leak the
    underlying ``httpx`` connection pool if the gateway call raises (e.g. 5xx
    propagates as ``httpx.HTTPStatusError`` and is converted to
    ``WorkflowRuntimeError`` by the runner).
    """
    rendered_prompt = render_jinja(config.prompt, inputs)
    messages: list[dict] = []
    if config.system_prompt:
        messages.append({"role": "system", "content": render_jinja(config.system_prompt, inputs)})
    messages.append({"role": "user", "content": rendered_prompt})

    client = AuditIsolationClient()
    try:
        resp = await client.chat(
            config.model,
            messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        content = resp["choices"][0]["message"]["content"]
        return {
            "content": content,
            "usage": resp.get("usage", {}),
            "raw": resp,
        }
    finally:
        await client.aclose()


__all__ = ["LLMConfig", "LLMNode", "llm_execute"]
