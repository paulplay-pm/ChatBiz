"""Dispatch a workflow run in workflow (single-shot) or chatflow (multi-turn) mode.

Both modes share the same compiled LangGraph ``StateGraph``; the difference
lives in the ``thread_id`` and how the LangGraph checkpointer treats it:

- ``workflow`` mode: fresh ``thread_id`` (``run-<uuid>``). The run starts
  from an empty checkpoint and terminates at ``END``. A single execution.
- ``chatflow`` mode: ``thread_id = session_id`` (or ``chat-<uuid>`` if no
  session). The LangGraph postgres checkpointer reads any prior
  checkpoint under that ``thread_id`` and resumes from there. This is
  the multi-turn human-in-the-loop pattern: an Approval node pauses
  execution, the approver UI re-enters via a new ``dispatch`` call with
  the same ``session_id``, and LangGraph picks up exactly where it left
  off.

The ``recursion_limit`` of 100 matches the eng-review safety budget
(finding #11: 4 critical paths, including the approval interrupt / resume
path, must be exercised end-to-end without runaway loops).
"""
from __future__ import annotations

import uuid
from typing import Any

from app.graph.compiler import compile_state_graph

_RECURSION_LIMIT = 100


async def dispatch(
    workflow_definition: dict,
    mode: str,
    session_id: str | None,
    initial_state: dict,
    workflow_id: str = "adhoc",
) -> dict:
    """Dispatch a workflow run.

    Args:
        workflow_definition: Canvas JSON, see ``compile_state_graph``.
        mode: ``"workflow"`` for a fresh single-shot run,
            ``"chatflow"`` for a multi-turn session that resumes from a
            prior checkpoint (sharing ``thread_id = session_id``).
        session_id: Required for ``chatflow`` mode (used as the
            ``thread_id``). Ignored for ``workflow`` mode (a random UUID
            is generated).
        initial_state: The starting state dict for the run. The runner
            (Task 6.1) injects ``_run_id`` and ``_workflow_variables``
            into this dict before calling ``dispatch``.
        workflow_id: Cache key for the compiled graph.

    Returns:
        The final state dict after the graph finishes (or hits the
        approval-interrupt boundary in chatflow mode).

    Raises:
        ValueError: if ``mode`` is not ``"workflow"`` or ``"chatflow"``.
        Whatever the underlying ``CompiledStateGraph.ainvoke`` raises.
    """
    if mode not in ("workflow", "chatflow"):
        raise ValueError(
            f"mode must be 'workflow' or 'chatflow', got {mode!r}"
        )

    compiled = compile_state_graph(workflow_definition, workflow_id=workflow_id)
    thread_id = build_thread_id(mode, session_id)

    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": _RECURSION_LIMIT,
    }
    return await compiled.ainvoke(initial_state, config=config)


def build_thread_id(mode: str, session_id: str | None) -> str:
    """Return the ``thread_id`` that ``dispatch()`` will use.

    Pure helper — useful for tests and for the runner to write the
    ``thread_id`` onto the ``workflow_run`` row *before* dispatching
    (so the SSE stream can locate the run by ``thread_id`` if needed).
    """
    if mode == "workflow":
        return f"run-{uuid.uuid4()}"
    return session_id or f"chat-{uuid.uuid4()}"


__all__ = ["dispatch", "build_thread_id"]
