"""Unit tests for ``app.llm.streaming`` — reverse_stream and buffer_and_reverse.

Uses monkeypatch to replace ``app.llm.streaming.reverse`` (imported from
``app.pii.reverser``) so no real Redis round-trip occurs.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.llm.streaming import buffer_and_reverse, reverse_stream


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_async_iter(*chunks: str):
    """Build an async iterator yielding the given string chunks."""

    async def _gen():
        for c in chunks:
            yield c

    return _gen()


# ---------------------------------------------------------------------------
# reverse_stream
# ---------------------------------------------------------------------------


class TestReverseStream:
    @pytest.mark.asyncio
    async def test_reverses_each_chunk(self, monkeypatch):
        """Each non-empty chunk is passed through reverse()."""
        calls: list[str] = []
        monkeypatch.setattr(
            "app.llm.streaming.reverse",
            AsyncMock(side_effect=lambda trace_id, text: calls.append(text)),
        )
        # Set a side effect that records calls AND returns a value
        async def _reverse(trace_id, text):
            calls.append(text)
            return f"rev:{text}"

        monkeypatch.setattr("app.llm.streaming.reverse", _reverse)

        chunks: list[str] = []
        async for chunk in reverse_stream("trace-1", _make_async_iter("hello", " world", "!")):
            chunks.append(chunk)

        assert chunks == ["rev:hello", "rev: world", "rev:!"]

    @pytest.mark.asyncio
    async def test_skips_empty_chunks(self, monkeypatch):
        """Empty string chunks are skipped, not passed to reverse."""
        processed: list[str] = []

        async def _reverse(trace_id, text):
            processed.append(text)
            return text

        monkeypatch.setattr("app.llm.streaming.reverse", _reverse)

        chunks: list[str] = []
        async for chunk in reverse_stream("trace-1", _make_async_iter("a", "", "b", "")):
            chunks.append(chunk)

        assert chunks == ["a", "b"]
        assert processed == ["a", "b"]

    @pytest.mark.asyncio
    async def test_empty_stream_yields_nothing(self, monkeypatch):
        """An empty async iterator yields nothing."""
        processed: list[str] = []

        async def _reverse(trace_id, text):
            processed.append(text)
            return text

        monkeypatch.setattr("app.llm.streaming.reverse", _reverse)

        chunks: list[str] = []
        async for chunk in reverse_stream("trace-1", _make_async_iter()):
            chunks.append(chunk)

        assert chunks == []
        assert processed == []

    @pytest.mark.asyncio
    async def test_passes_trace_id_to_reverse(self, monkeypatch):
        """The trace_id argument is forwarded to reverse()."""
        captured_trace_id = None

        async def _reverse(trace_id, text):
            nonlocal captured_trace_id
            captured_trace_id = trace_id
            return text

        monkeypatch.setattr("app.llm.streaming.reverse", _reverse)

        async for _ in reverse_stream("my-trace-id", _make_async_iter("chunk")):
            pass

        assert captured_trace_id == "my-trace-id"


# ---------------------------------------------------------------------------
# buffer_and_reverse
# ---------------------------------------------------------------------------


class TestBufferAndReverse:
    @pytest.mark.asyncio
    async def test_buffers_all_chunks_then_reverses_once(self, monkeypatch):
        """All chunks are joined and then reversed as a single string."""
        reversed_text = None
        captured_trace_id = None

        async def _reverse(trace_id, text):
            nonlocal reversed_text, captured_trace_id
            captured_trace_id = trace_id
            reversed_text = text
            return f"REVERSED:{text}"

        monkeypatch.setattr("app.llm.streaming.reverse", _reverse)

        result = await buffer_and_reverse(
            "trace-2",
            _make_async_iter("Hello ", "world", "!"),
        )

        assert captured_trace_id == "trace-2"
        assert reversed_text == "Hello world!"
        assert result == "REVERSED:Hello world!"

    @pytest.mark.asyncio
    async def test_empty_stream_returns_empty_string_reversed(self, monkeypatch):
        """An empty iterator results in an empty string passed to reverse."""
        reversed_text = None

        async def _reverse(trace_id, text):
            nonlocal reversed_text
            reversed_text = text
            return f"REVERSED:{text}"

        monkeypatch.setattr("app.llm.streaming.reverse", _reverse)

        result = await buffer_and_reverse("trace-3", _make_async_iter())

        assert reversed_text == ""
        assert result == "REVERSED:"

    @pytest.mark.asyncio
    async def test_single_chunk_buffered_identically(self, monkeypatch):
        """A single chunk produces the same result as reverse_stream for 1 chunk."""
        async def _reverse(trace_id, text):
            return f"[{text}]"

        monkeypatch.setattr("app.llm.streaming.reverse", _reverse)

        result = await buffer_and_reverse("t", _make_async_iter("single"))
        assert result == "[single]"
