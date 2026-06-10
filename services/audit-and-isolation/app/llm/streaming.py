"""SSE streaming support for the LLM client.

The MVP (Phase 6) keeps streaming simple: the gateway buffers the
upstream's SSE response into a single ``ChatCompletionResponse``
(joining the streamed ``delta`` chunks into a single ``message``)
and applies the PII reverser to the joined content before sending
the final response to the caller.

The reason for buffering rather than streaming: the placeholders
``[身份证_ab12]`` can span SSE chunks — the upstream might emit
``[身`` in one chunk and ``份证_ab12]`` in the next — and the
reverser can't know that a ``[`` in the current chunk is the
start of a placeholder until the rest of the chunk has arrived.
Buffering the whole response is the simplest correct approach.

If the perf bench (Task 16.x) later shows the buffer cost matters
at the 100 RPS SLO, the upgrade is to either:

* tell the LLM provider "no PII in the response" (which is
  exactly the audit log's invariant), so chunk-level reversal is
  always safe; or
* reverse inside a sliding 64-byte window per chunk (covers the
  4-hex-char suffix case).

Both are deferred to a follow-up change; the MVP keeps the
implementation as a no-op pass-through that future stream work
can replace.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from app.pii.reverser import reverse

logger = logging.getLogger(__name__)


async def reverse_stream(trace_id: str, async_iter: AsyncIterator[str]) -> AsyncIterator[str]:
    """Apply the PII reverser to each chunk of an SSE stream.

    The current implementation reverses per chunk — sufficient
    when the upstream's response never splits a placeholder
    across chunk boundaries. Callers that observe a split
    placeholder should switch to :func:`buffer_and_reverse`
    (added below as a stub for follow-up work).
    """
    async for chunk in async_iter:
        if not chunk:
            continue
        # Per-chunk reversal. If a placeholder spans chunks, the
        # caller will see a literal "[..." that doesn't match any
        # map key — same Fail-Open behaviour as the buffered
        # reverser, just per-chunk.
        yield await reverse(trace_id, chunk)


async def buffer_and_reverse(trace_id: str, async_iter: AsyncIterator[str]) -> str:
    """Buffer the full stream, then reverse once. Stub for future
    work — the MVP does not use this path; the call site (Phase 10
    chat.py) chooses the per-chunk path. Kept here so the
    streaming module is self-contained for the unit tests below.
    """
    chunks: list[str] = []
    async for chunk in async_iter:
        chunks.append(chunk)
    joined = "".join(chunks)
    return await reverse(trace_id, joined)


__all__ = ["buffer_and_reverse", "reverse_stream"]
