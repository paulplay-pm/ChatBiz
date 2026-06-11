"""Unit tests for ``app.models.llm`` — Pydantic v2 model construction, defaults,
validation, and optional fields.

No external dependencies are needed — these are pure data models.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.llm import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    Choice,
    Message,
    Usage,
)


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------


class TestMessage:
    def test_constructs_with_valid_role_and_content(self):
        m = Message(role="user", content="Hello, world!")
        assert m.role == "user"
        assert m.content == "Hello, world!"

    def test_rejects_invalid_role(self):
        with pytest.raises(ValidationError):
            Message(role="bot", content="Hello")

    def test_allows_system_user_assistant_roles(self):
        for role in ("system", "user", "assistant"):
            m = Message(role=role, content="test")
            assert m.role == role

    def test_accepts_empty_content(self):
        """Field(...) makes content required but has no min_length=1,
        so empty string is valid."""
        m = Message(role="user", content="")
        assert m.content == ""

    def test_rejects_content_over_max_length(self):
        with pytest.raises(ValidationError):
            Message(role="user", content="x" * 100_001)

    def test_content_at_exact_max_length_ok(self):
        m = Message(role="user", content="x" * 100_000)
        assert len(m.content) == 100_000

    def test_role_is_required(self):
        with pytest.raises(ValidationError):
            Message(content="no role")

    def test_content_is_required(self):
        with pytest.raises(ValidationError):
            Message(role="user")


# ---------------------------------------------------------------------------
# ChatCompletionRequest
# ---------------------------------------------------------------------------


class TestChatCompletionRequest:
    def test_minimal_constructs(self):
        req = ChatCompletionRequest(
            model="gpt-4o",
            messages=[Message(role="user", content="Hi")],
        )
        assert req.model == "gpt-4o"
        assert len(req.messages) == 1
        assert req.temperature is None
        assert req.max_tokens is None
        assert req.stream is False

    def test_full_constructs(self):
        req = ChatCompletionRequest(
            model="gpt-4o",
            messages=[
                Message(role="system", content="You are helpful."),
                Message(role="user", content="Hello"),
            ],
            temperature=0.7,
            max_tokens=2048,
            stream=True,
        )
        assert req.model == "gpt-4o"
        assert len(req.messages) == 2
        assert req.temperature == 0.7
        assert req.max_tokens == 2048
        assert req.stream is True

    def test_rejects_empty_model(self):
        with pytest.raises(ValidationError):
            ChatCompletionRequest(model="", messages=[Message(role="user", content="Hi")])

    def test_rejects_model_over_max_length(self):
        with pytest.raises(ValidationError):
            ChatCompletionRequest(model="x" * 201, messages=[Message(role="user", content="Hi")])

    def test_rejects_empty_messages(self):
        with pytest.raises(ValidationError):
            ChatCompletionRequest(model="gpt-4o", messages=[])

    def test_rejects_messages_over_max_length(self):
        with pytest.raises(ValidationError):
            ChatCompletionRequest(
                model="gpt-4o",
                messages=[Message(role="user", content="x")] * 1001,
            )

    def test_messages_exact_max_ok(self):
        req = ChatCompletionRequest(
            model="gpt-4o",
            messages=[Message(role="user", content="x")] * 1000,
        )
        assert len(req.messages) == 1000

    def test_temperature_boundaries(self):
        # ge=0.0, le=2.0
        ChatCompletionRequest(model="g", messages=[Message(role="user", content="x")], temperature=0.0)
        ChatCompletionRequest(model="g", messages=[Message(role="user", content="x")], temperature=2.0)

        with pytest.raises(ValidationError):
            ChatCompletionRequest(model="g", messages=[Message(role="user", content="x")], temperature=-0.1)
        with pytest.raises(ValidationError):
            ChatCompletionRequest(model="g", messages=[Message(role="user", content="x")], temperature=2.1)

    def test_max_tokens_boundaries(self):
        ChatCompletionRequest(model="g", messages=[Message(role="user", content="x")], max_tokens=1)
        ChatCompletionRequest(model="g", messages=[Message(role="user", content="x")], max_tokens=100_000)

        with pytest.raises(ValidationError):
            ChatCompletionRequest(model="g", messages=[Message(role="user", content="x")], max_tokens=0)
        with pytest.raises(ValidationError):
            ChatCompletionRequest(model="g", messages=[Message(role="user", content="x")], max_tokens=100_001)

    def test_stream_default_false(self):
        req = ChatCompletionRequest(model="g", messages=[Message(role="user", content="x")])
        assert req.stream is False


# ---------------------------------------------------------------------------
# Choice
# ---------------------------------------------------------------------------


class TestChoice:
    def test_constructs_with_all_fields(self):
        c = Choice(
            index=0,
            message=Message(role="assistant", content="Hello!"),
            finish_reason="stop",
        )
        assert c.index == 0
        assert c.message.role == "assistant"
        assert c.finish_reason == "stop"

    def test_finish_reason_defaults_to_none(self):
        c = Choice(index=0, message=Message(role="assistant", content="Hi"))
        assert c.finish_reason is None

    def test_finish_reason_accepts_null_explicitly(self):
        c = Choice(index=0, message=Message(role="assistant", content="Hi"), finish_reason=None)
        assert c.finish_reason is None

    def test_missing_required_fields_raises(self):
        with pytest.raises(ValidationError):
            Choice(index=0)
        with pytest.raises(ValidationError):
            Choice(message=Message(role="assistant", content="Hi"))


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


class TestUsage:
    def test_defaults_to_zero(self):
        u = Usage()
        assert u.prompt_tokens == 0
        assert u.completion_tokens == 0
        assert u.total_tokens == 0

    def test_constructs_with_custom_values(self):
        u = Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        assert u.prompt_tokens == 100
        assert u.completion_tokens == 50
        assert u.total_tokens == 150

    def test_partial_uses_defaults_for_missing(self):
        u = Usage(prompt_tokens=10)
        assert u.prompt_tokens == 10
        assert u.completion_tokens == 0
        assert u.total_tokens == 0


# ---------------------------------------------------------------------------
# ChatCompletionResponse
# ---------------------------------------------------------------------------


class TestChatCompletionResponse:
    def test_constructs_minimal_response(self):
        resp = ChatCompletionResponse(
            id="chatcmpl-123",
            created=1700000000,
            model="gpt-4o",
            choices=[],
            usage=Usage(),
        )
        assert resp.id == "chatcmpl-123"
        assert resp.object == "chat.completion"
        assert resp.created == 1700000000
        assert resp.model == "gpt-4o"
        assert resp.choices == []
        assert resp.usage.prompt_tokens == 0

    def test_object_defaults_to_chat_dot_completion(self):
        resp = ChatCompletionResponse(
            id="x",
            created=1,
            model="m",
            choices=[],
            usage=Usage(),
        )
        assert resp.object == "chat.completion"

    def test_object_can_be_overridden(self):
        resp = ChatCompletionResponse(
            id="x",
            object="chat.completion.chunk",
            created=1,
            model="m",
            choices=[],
            usage=Usage(),
        )
        assert resp.object == "chat.completion.chunk"

    def test_full_response_with_choices(self):
        resp = ChatCompletionResponse(
            id="chatcmpl-456",
            created=1700000001,
            model="gpt-4o",
            choices=[
                Choice(index=0, message=Message(role="assistant", content="Answer"), finish_reason="stop"),
            ],
            usage=Usage(prompt_tokens=20, completion_tokens=30, total_tokens=50),
        )
        assert len(resp.choices) == 1
        assert resp.choices[0].message.content == "Answer"
        assert resp.choices[0].finish_reason == "stop"
        assert resp.usage.total_tokens == 50

    def test_missing_required_fields_raises(self):
        with pytest.raises(ValidationError):
            ChatCompletionResponse(
                created=1,
                model="m",
                choices=[],
                usage=Usage(),
            )
        with pytest.raises(ValidationError):
            ChatCompletionResponse(
                id="x",
                model="m",
                choices=[],
                usage=Usage(),
            )
