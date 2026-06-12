"""Unit tests for app/errors/classes.py — ChatBizError + 10 subclasses."""
from app.errors.classes import (
    ChatBizError,
    SecurityError,
    UserError,
    WorkflowRuntimeError,
    NodeTypeNotRegisteredError,
    NodeOutputValidationError,
    CodeExecutionFailed,
    ApprovalNotFound,
    ApprovalAlreadyResponded,
    UnauthorizedApprovalAccess,
    WorkflowCycleError,
)


def test_chatbiz_error_default_class_and_message():
    e = ChatBizError("oops")
    assert e.error_class == "internal"
    assert e.message == "oops"
    assert e.context == {}
    assert str(e) == "oops"


def test_chatbiz_error_with_context():
    e = ChatBizError("oops", run_id="r1", user_id="u1")
    assert e.context == {"run_id": "r1", "user_id": "u1"}


def test_subclass_error_classes():
    """Each subclass declares the right error_class for the middleware status mapping."""
    assert SecurityError("x").error_class == "security"
    assert UserError("x").error_class == "user"
    assert WorkflowRuntimeError("x").error_class == "runtime"
    assert NodeTypeNotRegisteredError("foo").error_class == "user"
    assert NodeOutputValidationError("x").error_class == "runtime"
    assert CodeExecutionFailed("boom").error_class == "runtime"
    assert ApprovalNotFound("x").error_class == "user"
    assert ApprovalAlreadyResponded("x").error_class == "user"
    assert UnauthorizedApprovalAccess("x").error_class == "security"


def test_subclass_messages_preserved():
    assert str(SecurityError("denied")) == "denied"
    assert str(UserError("bad input")) == "bad input"
    assert str(WorkflowRuntimeError("LLM 5xx")) == "LLM 5xx"


def test_subclass_inherits_chatbiz_interface():
    e = ApprovalAlreadyResponded("responded", approval_id="a1")
    assert e.error_class == "user"
    assert e.context == {"approval_id": "a1"}


def test_subclass_isinstance_chatbizerror():
    e = CodeExecutionFailed("boom")
    assert isinstance(e, ChatBizError)
    assert isinstance(e, WorkflowRuntimeError)


# ---------- WorkflowCycleError (eng-review Quality #3 Boundary #1) ----------

def test_workflow_cycle_error_class():
    """WorkflowCycleError declares error_class='user' so the existing
    chatbiz_error_handler maps it to HTTP 422 + the unified response body.
    Independent class (not UserError subclass) for semantic clarity."""
    e = WorkflowCycleError([("a", "b"), ("b", "a")])
    assert e.error_class == "user"
    # Independent class — not a UserError subclass (eng-review D4 decision).
    assert type(e) is not UserError
    assert isinstance(e, ChatBizError)


def test_workflow_cycle_error_message_contains_edges():
    """The error message must contain the cycle edges so the API response
    body (which surfaces exc.message) tells the reviewer exactly which
    nodes form the loop without a server-side log dive."""
    edges = [("n1", "n2"), ("n2", "n3"), ("n3", "n1")]
    e = WorkflowCycleError(edges)
    assert "n1" in e.message
    assert "n2" in e.message
    assert "n3" in e.message
    assert "workflow contains cycle" in e.message


def test_workflow_cycle_error_preserves_edges_attr():
    """The exception carries the structured cycle_edges list so middleware
    and logs can introspect it (not just the rendered message)."""
    edges = (("a", "b"), ("b", "a"))
    e = WorkflowCycleError(list(edges))
    assert e.cycle_edges == [("a", "b"), ("b", "a")]


def test_workflow_cycle_error_defensive_copy():
    """Defensive copy: mutating the input list after construction must
    not affect the exception's stored cycle_edges (the spec asks for
    copy-on-construct to prevent late-stage logging surprises)."""
    src = [("a", "b"), ("b", "a")]
    e = WorkflowCycleError(src)
    src.append(("c", "a"))  # late append
    assert e.cycle_edges == [("a", "b"), ("b", "a")]
    assert len(src) == 3 and len(e.cycle_edges) == 2


def test_workflow_cycle_error_empty_edges():
    """Empty edge list is legal (e.g. detect_cycle returned []) — message
    must still be valid and the error must still raise."""
    e = WorkflowCycleError([])
    assert e.error_class == "user"
    assert "workflow contains cycle" in e.message
    assert e.cycle_edges == []
