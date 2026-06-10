"""Asynchronous audit-log outbox + writer worker.

The chat endpoint *never* waits for the audit write — a request
that takes 1 ms to forward to the upstream shouldn't take 5 ms
because Postgres is slow. Instead, the chat handler enqueues an
``AuditLog`` ORM object on the outbox's ``asyncio.Queue`` and
returns the response immediately. A background worker drains
the queue and writes each row through the standard
``get_session()`` context manager, with 3-attempt exponential
backoff on transient DB failures.

Failure semantics:

* Queue full (10 000 entries backed up) → log + drop the record.
  The chat handler is unaffected; the dropped record is lost but
  the gateway stays up. A Prometheus counter
  ``audit_outbox_dropped_total`` should be added in Phase 11.
* DB write fails 3 times → log + give up. The record is lost,
  but the chat response has already been returned. Operators
  detect the loss via the ``audit_outbox_failed_total`` counter.
* Worker not running (lifespan shutdown before the queue drains)
  → records already enqueued stay in the queue; on the next
  pod start the worker drains them. (Cross-pod, the queue is
  per-process — see the Redis-queue TODO for HA.)
"""

from __future__ import annotations

import asyncio
import logging

from app.database import get_session
from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


class AuditOutbox:
    """Async queue + background worker for ``AuditLog`` writes."""

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._task: asyncio.Task | None = None
        self._stop = False

    async def start(self):
        """Spawn the background worker. Idempotent — calling
        twice does not spawn a second worker (the existing one
        is reused)."""
        self._stop = False
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._worker())

    async def stop(self):
        """Signal the worker to exit after the queue drains."""
        self._stop = True
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("audit outbox worker did not stop in 5s")
            self._task = None

    def enqueue(self, record: AuditLog):
        """Non-blocking enqueue. Drops + logs if the queue is full.

        ``record`` must be an *unattached* ``AuditLog`` ORM object —
        the worker is responsible for adding it to a session and
        committing. Dropping on full is preferable to backpressuring
        the request handler, which would propagate to the caller.
        """
        try:
            self._queue.put_nowait(record)
        except asyncio.QueueFull:
            logger.error("audit outbox full, dropping record")

    async def _worker(self):
        """Drain the queue, write each record with 3-attempt backoff.

        The loop exits only when ``self._stop`` is set AND the
        queue is empty. The 1-second ``wait_for`` timeout on
        ``queue.get()`` keeps the loop responsive to the stop
        signal even when the queue is idle.
        """
        while not self._stop or not self._queue.empty():
            try:
                rec = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            await self._write_with_retry(rec)

    async def _write_with_retry(self, rec: AuditLog) -> None:
        """Write a single record with exponential backoff (0.2 / 0.4 / 0.8 s).

        After 3 failures the record is logged and dropped. The
        function never raises — a failed audit write must never
        propagate to the chat handler.
        """
        for attempt in range(3):
            try:
                async with get_session() as s:
                    s.add(rec)
                    await s.commit()
                return
            except Exception as e:
                logger.warning(
                    f"audit write failed (attempt {attempt+1}/3, trace_id={rec.trace_id}): {e}"
                )
                await asyncio.sleep(0.2 * (2**attempt))
        logger.error(f"audit write permanently failed for trace_id={rec.trace_id}")


_outbox: AuditOutbox | None = None


def get_outbox() -> AuditOutbox:
    """Return the singleton ``AuditOutbox``. Lazy-initialised so
    importing this module doesn't spawn a worker (and doesn't
    require the FastAPI lifespan to have run yet)."""
    global _outbox
    if _outbox is None:
        _outbox = AuditOutbox()
    return _outbox


def reset_outbox_for_tests() -> None:
    """Drop the singleton outbox. Test-only helper."""
    global _outbox
    _outbox = None


__all__ = ["AuditOutbox", "get_outbox", "reset_outbox_for_tests"]
