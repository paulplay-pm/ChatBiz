"""Unit tests for app/errors/classes.py — ChatBizError + 9 subclasses."""
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
    assert CodeExecutionFailed("x").error_class == "runtime"
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
