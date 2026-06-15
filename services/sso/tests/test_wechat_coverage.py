"""Coverage-gap tests for sso/wechat.py.

Per `openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md`
§3.1 + §4.1 row 3, `app/wechat.py` had 8 missing lines across
5 paths. This file adds 5 tests to close the gap to 100% line cov.

Pattern follows `services/sso/tests/test_coverage_followup.py` and
`services/sso/tests/test_routers_coverage.py` (commits 5d895e6 / 23018e8).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


def _make_wechat_client():
    """Build a real WeChatClient instance with placeholder credentials
    (so _available == True)."""
    from app.wechat import WeChatClient
    return WeChatClient(
        corp_id="test_corp", agent_id="test_agent",
        corp_secret="test_secret", redirect_uri="http://x",
    )


def _make_httpx_mock(get_return=None, get_side_effect=None):
    """Build a mock httpx.AsyncClient that yields a context manager whose
    `get` is a configured AsyncMock. Pass either get_return (httpx.Response
    MagicMock) or get_side_effect (exception class instance).
    """
    mock_http = MagicMock()
    if get_side_effect is not None:
        mock_http.get = AsyncMock(side_effect=get_side_effect)
    else:
        mock_http.get = AsyncMock(return_value=get_return)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    return mock_http


# =============================================================================
# app/wechat.py::exchange_code — line 71-74 (TimeoutException)
# =============================================================================


def test_exchange_code_timeout_exception() -> None:
    """Lines 71-74: exchange_code converts httpx.TimeoutException to
    WorkflowRuntimeError(code='runtime.wechat_timeout').
    """
    from app.jwt_utils import WorkflowRuntimeError
    client = _make_wechat_client()
    with patch("httpx.AsyncClient") as mock_httpx_client:
        mock_httpx_client.return_value = _make_httpx_mock(
            get_side_effect=httpx.TimeoutException("read timeout"),
        )
        with pytest.raises(WorkflowRuntimeError) as exc_info:
            asyncio.run(client.exchange_code("code"))
        assert exc_info.value.code == "runtime.wechat_timeout"
        assert "timeout" in str(exc_info.value)


# =============================================================================
# app/wechat.py::exchange_code — line 75-77 (HTTPError)
# =============================================================================


def test_exchange_code_http_error() -> None:
    """Lines 75-77: exchange_code converts httpx.HTTPError to
    WorkflowRuntimeError(code='runtime.wechat_5xx').
    """
    from app.jwt_utils import WorkflowRuntimeError
    client = _make_wechat_client()
    with patch("httpx.AsyncClient") as mock_httpx_client:
        mock_httpx_client.return_value = _make_httpx_mock(
            get_side_effect=httpx.HTTPError("connection error"),
        )
        with pytest.raises(WorkflowRuntimeError) as exc_info:
            asyncio.run(client.exchange_code("code"))
        assert exc_info.value.code == "runtime.wechat_5xx"
        assert "HTTP error" in str(exc_info.value)


# =============================================================================
# app/wechat.py::exchange_code — line 88-90 (other errcode)
# =============================================================================


def test_exchange_code_other_errcode() -> None:
    """Lines 88-90: exchange_code converts errcode not in (40029, 40163)
    to WorkflowRuntimeError(code='runtime.wechat_5xx').
    """
    from app.jwt_utils import WorkflowRuntimeError
    client = _make_wechat_client()
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = {"errcode": 50005, "errmsg": "freq limit"}
    mock_response.raise_for_status = MagicMock()
    with patch("httpx.AsyncClient") as mock_httpx_client:
        mock_httpx_client.return_value = _make_httpx_mock(get_return=mock_response)
        with pytest.raises(WorkflowRuntimeError) as exc_info:
            asyncio.run(client.exchange_code("code"))
        assert exc_info.value.code == "runtime.wechat_5xx"
        assert "50005" in str(exc_info.value)
        assert "freq limit" in str(exc_info.value)


# =============================================================================
# app/wechat.py::exchange_code — line 95-97 (missing field)
# =============================================================================


def test_exchange_code_missing_access_token() -> None:
    """Lines 95-97: exchange_code raises WorkflowRuntimeError when response
    errcode=0 but access_token or openid field is missing.
    """
    from app.jwt_utils import WorkflowRuntimeError
    client = _make_wechat_client()
    mock_response = MagicMock(spec=httpx.Response)
    # errcode=0 happy, but missing access_token
    mock_response.json.return_value = {"errcode": 0, "openid": "openid-1"}
    mock_response.raise_for_status = MagicMock()
    with patch("httpx.AsyncClient") as mock_httpx_client:
        mock_httpx_client.return_value = _make_httpx_mock(get_return=mock_response)
        with pytest.raises(WorkflowRuntimeError) as exc_info:
            asyncio.run(client.exchange_code("code"))
        assert exc_info.value.code == "runtime.wechat_5xx"
        assert "缺字段" in str(exc_info.value)


# =============================================================================
# app/wechat.py::fetch_userinfo — line 114-115 (httpx exception via try/except)
# =============================================================================


def test_fetch_userinfo_httpx_error() -> None:
    """Lines 114-115: fetch_userinfo converts httpx.HTTPError to
    WorkflowRuntimeError(code='runtime.wechat_5xx') via try/except block.

    Note: existing test_coverage_followup.py test mocks WeChatClient.fetch_userinfo
    directly (side_effect on client method) which BYPASSES the try/except block.
    This test mocks httpx.AsyncClient.get instead so the try/except body is hit.
    """
    from app.jwt_utils import WorkflowRuntimeError
    client = _make_wechat_client()
    with patch("httpx.AsyncClient") as mock_httpx_client:
        mock_httpx_client.return_value = _make_httpx_mock(
            get_side_effect=httpx.HTTPError("conn refused"),
        )
        with pytest.raises(WorkflowRuntimeError) as exc_info:
            asyncio.run(client.fetch_userinfo("tok", "openid-1"))
        assert exc_info.value.code == "runtime.wechat_5xx"
        assert "userinfo" in str(exc_info.value)
