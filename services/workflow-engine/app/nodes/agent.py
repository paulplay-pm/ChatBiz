"""Agent node — dispatch a task to the agent-runtime service.

Calls the agent-runtime service's ``/invoke`` endpoint via the stub client in
``app/clients/agent_runtime.py``. The agent-runtime ships in a later change
(``implement-agent-runtime``); the stub returns 503 until then.

This is the **only** node type that runs the Lead Agent / Sub Agent
orchestration pattern (see ``docs/architecture.md`` §4.3.2) — a single
``agent`` invocation can spin up a Sub Agent with ``tools`` available and
iterate up to ``max_iterations`` times before returning a final answer.
"""
from __future__ import annotations

from pydantic import Field

from app.clients.agent_runtime import AgentRuntimeClient
from app.graph.jinja import render_jinja
from app.nodes.contracts.base import BaseConfig, BaseNode
from app.nodes.registry import register


class AgentConfig(BaseConfig):
    """Configuration for the agent-runtime invocation node."""

    agent_id: str = Field(..., description="Agent 类型 ID (e.g. 'financial-report-writer')")
    task: str = Field(..., description="Jinja2 任务描述模板,渲染后作为 agent 入口 prompt")
    max_iterations: int = Field(10, ge=1, le=100, description="Sub Agent 最大迭代次数")
    tools: list[str] = Field(
        default_factory=list,
        description="可用工具列表 (e.g. ['kb_search', 'sql_query']);空 = 取决于 agent 默认配置",
    )


@register("agent", version="1.0.0")
class AgentNode(BaseNode):
    """Node contract for the agent-runtime invocation node."""

    config: AgentConfig


async def agent_execute(config: AgentConfig, inputs: dict) -> dict:
    """Render the task template, dispatch to agent-runtime, return the parsed body."""
    rendered_task = render_jinja(config.task, inputs)
    client = AgentRuntimeClient()
    try:
        resp = await client.invoke(
            config.agent_id,
            rendered_task,
            max_iterations=config.max_iterations,
            tools=config.tools,
        )
        return resp
    finally:
        await client.aclose()


__all__ = ["AgentConfig", "AgentNode", "agent_execute"]
