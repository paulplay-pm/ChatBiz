"""Typed exception classes for the workflow-engine service.

Every error raised in the workflow-engine has a class on this module
so the FastAPI exception handlers (added in a later task) can map it
to the right HTTP status + audit-log severity. The hierarchy mirrors
the 4-boundary error model from the eng-review report
(``docs/architecture.md`` §4 + design doc finding #9):

* ``SecurityError`` — boundary #4 (security / 未授权凭证). 403.
* ``UserError`` — boundary #3 (user / 参数不全). 400.
* ``WorkflowRuntimeError`` — boundary #2 (runtime / LLM 5xx /
  timeout / 限额). 502 or 504 depending on subtype.

The base class ``ChatBizError`` carries a ``context`` dict for
structured fields (e.g. ``{"credential_id": "..."}``) so the audit
log can capture them.

Naming note: ``WorkflowRuntimeError`` is *not* the built-in
``RuntimeError``. The built-in is a bare ``Exception`` with no
context field; we want our typed hierarchy to own the runtime-error
namespace inside this service.
"""

from __future__ import annotations

from typing import Any


class ChatBizError(Exception):
    """Base class for all workflow-engine typed errors.

    Carries a free-form ``context`` dict that exception handlers and
    the audit log can serialize alongside the message.
    """

    error_class: str = "internal"

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.context = context


class SecurityError(ChatBizError):
    """Boundary #4: 未授权凭证 / 越权访问. Mapped to HTTP 403."""

    error_class = "security"


class UserError(ChatBizError):
    """Boundary #3: 用户输入参数不全 / 校验失败. Mapped to HTTP 400."""

    error_class = "user"


class WorkflowRuntimeError(ChatBizError):
    """Boundary #2: 运行时故障 (LLM 5xx / timeout / 限额). Mapped to HTTP 502/504.

    Note: this is **not** the built-in ``RuntimeError`` — we own the
    ``WorkflowRuntimeError`` namespace so all runtime failures in the
    engine carry the structured ``context`` field.
    """

    error_class = "runtime"


class NodeTypeNotRegisteredError(UserError):
    """A workflow references a node type that is not in the registry."""

    error_class = "user"


class NodeOutputValidationError(WorkflowRuntimeError):
    """A node produced output that fails its declared output schema."""

    error_class = "runtime"


class CodeExecutionFailed(WorkflowRuntimeError):
    """A Code node's docker / subprocess execution failed."""

    error_class = "runtime"


class ApprovalNotFound(UserError):
    """No pending approval record matches the given workflow + step id."""

    error_class = "user"


class ApprovalAlreadyResponded(UserError):
    """The approval record has already been approved or rejected."""

    error_class = "user"


class UnauthorizedApprovalAccess(SecurityError):
    """The current user is not the assigned approver for this approval."""

    error_class = "security"


class WorkflowCycleError(ChatBizError):
    """Boundary #1 (eng-review Quality #3): canvas drag-loop prevention.

    Raised when ``services/workflow-engine/app/errors/cycle_detection.py``
    finds a cycle in the workflow DAG. The ``cycle_edges`` list is
    serialised into ``error_message`` so the API response carries the
    exact edges that form the loop (helps reviewers locate it without
    server-side logs).

    Mapped to HTTP 422 by the middleware; ``error_class`` stays
    ``"user"`` to keep the 4-boundary contract flat (canvas is a user
    action; the cycle is a validation failure of that action).
    """

    error_class = "user"

    def __init__(self, cycle_edges: list[tuple[str, str]]) -> None:
        # Re-render as JSON-ish so the message survives logging and the
        # middleware round-trip without losing structure.
        msg = f"workflow contains cycle: {list(cycle_edges)}"
        super().__init__(msg)
        self.cycle_edges = list(cycle_edges)


__all__ = [
    "ChatBizError",
    "SecurityError",
    "UserError",
    "WorkflowRuntimeError",
    "NodeTypeNotRegisteredError",
    "NodeOutputValidationError",
    "CodeExecutionFailed",
    "ApprovalNotFound",
    "ApprovalAlreadyResponded",
    "UnauthorizedApprovalAccess",
    "WorkflowCycleError",
]
