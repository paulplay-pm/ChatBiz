"""Human-approval node — pause the workflow for human sign-off.

This node marks the workflow as paused. The *actual* persistence of the
approval row + the WeCom / email / in-app notification is done by the
workflow runner (``executor/runner.py``), not here. We keep this node's
execute function pure: it renders the notification content template and
returns the metadata the runner needs to write the approval row.

The pause/resume lifecycle is handled by LangGraph's ``interrupt_before``
mechanism with a PostgreSQL checkpointer (see eng-review finding #6):

* The runner registers this node's id with ``interrupt_before=[node_id]``
  so LangGraph pauses *before* executing the node's body.
* A separate ``POST /api/approvals/:id/respond`` endpoint writes the
  decision to the ``approvals`` table and calls ``graph.invoke(None,
  config)`` to resume.
* If ``timeout_hours`` elapses without a response, the runner fires
  escalation notifications and the workflow remains paused (no auto-reject
  for MVP — the user-configurable timeout policy is Phase 5).
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.graph.jinja import render_jinja
from app.nodes.contracts.base import BaseConfig, BaseNode
from app.nodes.registry import register


class ApprovalConfig(BaseConfig):
    """Configuration for the human-approval node."""

    approver_user_id: str = Field(..., description="审批人 user_id (workflow 启动时校验存在)")
    timeout_hours: int = Field(24, ge=1, le=720, description="审批超时 (h);到期触发 escalation 通知")
    notify_channels: list[Literal["wecom", "email", "in_app"]] = Field(
        default_factory=lambda: ["wecom"],
        description="通知渠道;MVP 至少需要 1 个,WeCom 是默认",
    )
    approval_content_template: str = Field(
        ...,
        description="Jinja2 通知内容模板,渲染后作为审批详情(包含上下文数据,供审批人决策)",
    )


@register("approval", version="1.0.0")
class ApprovalNode(BaseNode):
    """Node contract for the human-approval node."""

    config: ApprovalConfig


async def approval_execute(config: ApprovalConfig, inputs: dict) -> dict:
    """Render the notification content; return metadata for the runner to persist.

    The runner reads ``pending=True`` to know it should create an approval row
    in the ``approvals`` table and fire the configured ``notify_channels``.
    The runner reads ``content`` to put in the WeCom / email / in-app
    notification body.
    """
    content = render_jinja(config.approval_content_template, inputs)
    return {
        "pending": True,
        "approver_user_id": config.approver_user_id,
        "content": content,
        "timeout_hours": config.timeout_hours,
        "notify_channels": list(config.notify_channels),
    }


__all__ = ["ApprovalConfig", "ApprovalNode", "approval_execute"]
