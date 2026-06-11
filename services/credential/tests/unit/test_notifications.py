"""Unit tests for ``app.notifications`` — 企微 webhook transport."""

from __future__ import annotations

import logging
from typing import Any

import httpx
import pytest
import respx
from httpx import Response


from app.notifications import DEFAULT_TIMEOUT_SECONDS, send_wechat_webhook

DUMMY_MESSAGE: dict[str, Any] = {
    "msgtype": "text",
    "text": {"content": "credential expiring: test-key"},
}


@pytest.mark.asyncio
class TestSendWechatWebhook:
    async def test_empty_url_noop(self, caplog) -> None:  # type: ignore[no-untyped-def]
        """Empty URL returns immediately without sending."""
        caplog.set_level(logging.DEBUG)
        await send_wechat_webhook(None, DUMMY_MESSAGE)
        assert any("empty URL" in r.message for r in caplog.records)

    async def test_none_url_noop(self, caplog) -> None:  # type: ignore[no-untyped-def]
        """None URL returns immediately without sending."""
        caplog.set_level(logging.DEBUG)
        await send_wechat_webhook(None, DUMMY_MESSAGE)
        assert any("empty URL" in r.message for r in caplog.records)

    @respx.mock
    async def test_successful_post(self) -> None:
        """Successful POST logs no warnings."""
        url = "https://qyapi.weixin.qq.com/webhook/test"
        respx.post(url).mock(return_value=Response(200))

        # Should not raise.
        await send_wechat_webhook(url, DUMMY_MESSAGE)

        # Verify the request was made.
        assert respx.calls.call_count == 1
        last = respx.calls.last
        assert last is not None
        assert last.request.url == url

    @respx.mock
    async def test_4xx_response_logs_warning(self, caplog) -> None:  # type: ignore[no-untyped-def]
        """4xx response logs a warning but does NOT raise."""
        url = "https://qyapi.weixin.qq.com/webhook/bad"
        respx.post(url).mock(return_value=Response(400, text="Bad Request"))

        caplog.set_level(logging.WARNING)
        await send_wechat_webhook(url, DUMMY_MESSAGE)
        assert any("returned 400" in r.message for r in caplog.records)

    @respx.mock
    async def test_5xx_response_logs_warning(self, caplog) -> None:  # type: ignore[no-untyped-def]
        """5xx response logs a warning but does NOT raise."""
        url = "https://qyapi.weixin.qq.com/webhook/error"
        respx.post(url).mock(return_value=Response(500, text="Internal Error"))

        caplog.set_level(logging.WARNING)
        await send_wechat_webhook(url, DUMMY_MESSAGE)
        assert any("returned 500" in r.message for r in caplog.records)

    @respx.mock
    async def test_transport_error_logs_warning(self, caplog) -> None:  # type: ignore[no-untyped-def]
        """httpx.HTTPError (transport failure) logs a warning but does NOT raise."""
        url = "https://qyapi.weixin.qq.com/webhook/unreachable"
        respx.post(url).mock(side_effect=httpx.ConnectError("connection refused"))

        caplog.set_level(logging.WARNING)
        await send_wechat_webhook(url, DUMMY_MESSAGE)
        assert any("transport error" in r.message for r in caplog.records)
        assert any("failed wechat payload" in r.message for r in caplog.records)

    @respx.mock
    async def test_timeout_error_logs_warning(self, caplog) -> None:  # type: ignore[no-untyped-def]
        """httpx.TimeoutException logs a warning but does NOT raise."""
        url = "https://qyapi.weixin.qq.com/webhook/slow"
        respx.post(url).mock(side_effect=httpx.TimeoutException("timed out"))

        caplog.set_level(logging.WARNING)
        await send_wechat_webhook(url, DUMMY_MESSAGE)
        assert any("transport error" in r.message for r in caplog.records)

    @respx.mock
    async def test_default_timeout_is_10_seconds(self) -> None:
        """Verify the default timeout constant."""
        assert DEFAULT_TIMEOUT_SECONDS == 10.0

    @respx.mock
    async def test_response_body_truncated_in_log(self, caplog) -> None:  # type: ignore[no-untyped-def]
        """Response body in warning log is truncated to 200 chars."""
        url = "https://qyapi.weixin.qq.com/webhook/verbose"
        respx.post(url).mock(return_value=Response(400, text="x" * 500))

        caplog.set_level(logging.WARNING)
        await send_wechat_webhook(url, DUMMY_MESSAGE)
        # The log message should contain the truncated text.
        assert any("returned 400" in r.message for r in caplog.records)
