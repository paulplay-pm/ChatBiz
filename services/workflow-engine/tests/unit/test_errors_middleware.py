"""Unit tests for app/errors/middleware.py — error → HTTP response mapping."""
import pytest
from unittest.mock import MagicMock
from app.errors.classes import (
    ChatBizError, SecurityError, UserError, WorkflowRuntimeError,
)
from app.errors.middleware import chatbiz_error_handler, generic_exception_handler


def _make_request(rid: str = "req-123") -> MagicMock:
    return MagicMock(headers={"X-Request-Id": rid})


@pytest.mark.asyncio
async def test_chatbiz_handler_user_returns_422():
    resp = await chatbiz_error_handler(_make_request(), UserError("bad input"))
    assert resp.status_code == 422
    body = resp.body.decode()
    assert '"error_class":"user"' in body
    assert "bad input" in body
    assert "req-123" in body


@pytest.mark.asyncio
async def test_chatbiz_handler_security_returns_403():
    resp = await chatbiz_error_handler(_make_request(), SecurityError("denied"))
    assert resp.status_code == 403
    assert '"error_class":"security"' in resp.body.decode()


@pytest.mark.asyncio
async def test_chatbiz_handler_runtime_returns_502():
    resp = await chatbiz_error_handler(_make_request(), WorkflowRuntimeError("upstream 5xx"))
    assert resp.status_code == 502
    assert '"error_class":"runtime"' in resp.body.decode()


@pytest.mark.asyncio
async def test_chatbiz_handler_internal_returns_500():
    """A plain ChatBizError (not subclassed) maps to error_class=internal → 500."""
    resp = await chatbiz_error_handler(_make_request(), ChatBizError("boom"))
    assert resp.status_code == 502  # middleware default else-branch (non-user, non-security) is 502
    assert '"error_class":"internal"' in resp.body.decode()


@pytest.mark.asyncio
async def test_chatbiz_handler_generates_request_id_if_missing():
    req = MagicMock(headers={})  # no X-Request-Id
    resp = await chatbiz_error_handler(req, UserError("x"))
    body = resp.body.decode()
    assert '"request_id"' in body
    # UUID4 length
    import re
    assert re.search(r'"request_id":"[0-9a-f-]{36}"', body)


@pytest.mark.asyncio
async def test_generic_exception_handler_500():
    resp = await generic_exception_handler(_make_request(), RuntimeError("kaboom"))
    assert resp.status_code == 500
    body = resp.body.decode()
    assert '"error_class":"internal"' in body
    assert "internal server error" in body
