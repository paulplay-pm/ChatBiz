"""Unit tests for the integration-test echo bypass in audit-and-isolation.

The echo bypass lets integration tests exercise the audit-and-isolation
egress gateway without a real LLM upstream. The bypass is gated by
``settings.environment == "integration"`` AND ``body.model == "echo-test"``;
production paths are unaffected.

These tests do NOT need the full docker stack — they directly import the
module and patch the settings + the audit outbox.
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

import orjson
import pytest
from fastapi import HTTPException

# Ensure the integration env is set BEFORE importing the module so the
# gate evaluates correctly.
os.environ.setdefault("ENVIRONMENT", "integration")


@pytest.fixture
def settings():
    """Override Settings via env so .environment reads 'integration'."""
    with patch.dict(
        os.environ,
        {
            "DATABASE_URL": "postgresql+asyncpg://test",
            "REDIS_URL": "redis://test",
            "CREDENTIAL_SERVICE_URL": "http://test",
            "ENVIRONMENT": "integration",
        },
        clear=False,
    ):
        from app.config import get_settings

        get_settings.cache_clear()
        yield get_settings()


@pytest.fixture
def fake_outbox():
    """Replace the audit outbox with a mock that captures enqueued rows."""
    outbox = MagicMock()
    with patch("app.api.chat.get_outbox", return_value=outbox):
        yield outbox


def _make_header(trace_id: str = "test-trace-12345678"):
    from app.models.common import HeaderSchema

    return HeaderSchema(
        trace_id=trace_id,
        model_kind="private",
        bypass_isolation=False,
    )


def _user_id() -> str:
    return "u-test"


def test_echo_bypass_returns_openai_shape(settings, fake_outbox):
    from app.api.chat import _maybe_echo_bypass

    body = {
        "model": "echo-test",
        "messages": [{"role": "user", "content": "hello world"}],
    }
    header = _make_header()

    resp = _maybe_echo_bypass(body, header, _user_id())

    assert resp is not None
    assert resp.status_code == 200
    data = orjson.loads(resp.body)
    assert data["model"] == "echo-test"
    assert data["choices"][0]["message"]["content"] == "ECHO: hello world"
    assert data["choices"][0]["finish_reason"] == "stop"
    assert "usage" in data
    assert data["usage"]["completion_tokens"] > 0
    assert data["usage"]["prompt_tokens"] > 0


def test_echo_bypass_writes_audit_log(settings, fake_outbox):
    from app.api.chat import _maybe_echo_bypass

    body = {
        "model": "echo-test",
        "messages": [{"role": "user", "content": "audit me"}],
    }
    header = _make_header(trace_id="audit-trace-aaaa-bbbb")

    resp = _maybe_echo_bypass(body, header, _user_id())

    assert resp is not None
    # Verify audit outbox was called with the right shape
    fake_outbox.enqueue.assert_called_once()
    audit = fake_outbox.enqueue.call_args[0][0]
    assert audit.model == "echo-test"
    assert audit.trace_id == "audit-trace-aaaa-bbbb"
    assert audit.user_id == "u-test"
    assert audit.workflow_id is None
    assert audit.upstream_status == 200
    assert audit.error_class is None
    assert audit.pii_detected_types == []  # bypass skips PII


def test_echo_bypass_returns_none_for_real_model(settings, fake_outbox):
    """Production model names must NOT be intercepted by the bypass."""
    from app.api.chat import _maybe_echo_bypass

    body = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "hi"}],
    }
    header = _make_header()

    resp = _maybe_echo_bypass(body, header, _user_id())

    assert resp is None
    fake_outbox.enqueue.assert_not_called()


def test_echo_bypass_returns_none_for_other_model_name(settings, fake_outbox):
    """Non-echo-test model names must NOT be intercepted."""
    from app.api.chat import _maybe_echo_bypass

    body = {
        "model": "claude-3",  # close but not the sentinel
        "messages": [{"role": "user", "content": "hi"}],
    }
    header = _make_header()

    resp = _maybe_echo_bypass(body, header, _user_id())

    assert resp is None
    fake_outbox.enqueue.assert_not_called()


def test_echo_bypass_disabled_in_production(settings, fake_outbox):
    """With environment=production, the bypass is fully off."""
    with patch.dict(
        os.environ,
        {"ENVIRONMENT": "production"},
        clear=False,
    ):
        from app.config import get_settings

        get_settings.cache_clear()
        from app.api.chat import _maybe_echo_bypass

        body = {
            "model": "echo-test",
            "messages": [{"role": "user", "content": "hello"}],
        }
        header = _make_header()

        resp = _maybe_echo_bypass(body, header, _user_id())

        assert resp is None
        fake_outbox.enqueue.assert_not_called()


def test_echo_bypass_handles_empty_messages(settings, fake_outbox):
    from app.api.chat import _maybe_echo_bypass

    body = {"model": "echo-test", "messages": []}
    header = _make_header()

    resp = _maybe_echo_bypass(body, header, _user_id())

    assert resp is not None
    data = orjson.loads(resp.body)
    assert data["choices"][0]["message"]["content"] == "ECHO: <empty>"


def test_echo_bypass_picks_last_user_message(settings, fake_outbox):
    from app.api.chat import _maybe_echo_bypass

    body = {
        "model": "echo-test",
        "messages": [
            {"role": "system", "content": "you are helpful"},
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "ack"},
            {"role": "user", "content": "second"},
        ],
    }
    header = _make_header()

    resp = _maybe_echo_bypass(body, header, _user_id())

    assert resp is not None
    data = orjson.loads(resp.body)
    assert data["choices"][0]["message"]["content"] == "ECHO: second"
