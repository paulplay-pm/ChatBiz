"""Pydantic v2 models for OpenAI-compatible chat completion I/O.

The shapes here mirror the OpenAI ``/v1/chat/completions`` schema. The
gateway never invents a new wire shape: callers submit a standard
``ChatCompletionRequest`` (validated, with size caps) and the gateway
forwards a redacted version upstream. The upstream's response is parsed
back into ``ChatCompletionResponse`` so the gateway can apply
place-holder reversal consistently before returning to the caller.

The schema is intentionally a strict subset of the OpenAI surface — the
plan Task 3.1 only models the fields the rest of the gateway actually
reads (``model`` / ``messages`` / ``temperature`` / ``max_tokens`` /
``stream``). Forwarding unknown fields is delegated to the upstream
(``httpx`` passes the original ``body`` dict through to ``client.post``);
these Pydantic models are for *validation* and *typed parsing* of the
gates, not for exhaustive round-tripping.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single chat message. The 100 000-char cap mirrors the OpenAI
    limit (and keeps the SHA-256 prompt-hash fast to compute on a
    worst-case body of 1 000 messages)."""

    role: Literal["system", "user", "assistant"]
    content: str = Field(..., max_length=100_000)


class ChatCompletionRequest(BaseModel):
    """Inbound chat-completion request body.

    ``stream`` is kept on the schema for future Phase 6 streaming work
    (Task 7.2); the non-streaming code path ignores it for now and the
    gateway always returns a buffered ``ChatCompletionResponse``.
    """

    model: str = Field(..., min_length=1, max_length=200)
    messages: list[Message] = Field(..., min_length=1, max_length=1000)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=100_000)
    stream: bool = False


class Choice(BaseModel):
    """A single completion choice. ``finish_reason`` matches OpenAI's
    nullable string (``"stop"`` / ``"length"`` / ``"tool_calls"`` / etc.)."""

    index: int
    message: Message
    finish_reason: str | None = None


class Usage(BaseModel):
    """Token accounting. Defaults to 0 so an upstream that omits
    ``usage`` (some providers do under error conditions) still parses."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """Outbound response body. ``object`` is the OpenAI literal."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage


__all__ = [
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "Choice",
    "Message",
    "Usage",
]
