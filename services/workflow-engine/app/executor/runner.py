"""Workflow execution runner.

The runner is the entry point for actually running a workflow. It owns
the ``workflow_run`` row lifecycle:

1. Pre-flight: credential ACL check for every node that uses a
   credential. Fails fast with ``SecurityError`` *before* the graph
   starts (avoids paying LLM costs only to 403 on node 14).
2. Status transitions: ``pending`` -> ``running`` -> (``completed`` /
   ``failed``). Each transition is a single SQL UPDATE inside its own
   session.
3. Graph dispatch: ``app.graph.dispatcher.dispatch`` runs the compiled
   ``StateGraph`` to completion (or to an approval interrupt).
4. Error capture: any exception from the graph is mapped onto the run
   row's ``error_class`` + ``error_message`` columns, then re-raised so
   the caller (FastAPI endpoint or background task) can log / 500.

Two public entry points:

- ``run_workflow`` — coroutine. Awaits the run to completion.
- ``schedule_run`` — sync helper. Generates a ``run_id`` and schedules
  ``run_workflow`` as a background ``asyncio.create_task`` task. Returns
  the ``run_id`` immediately so the HTTP response can stream progress
  via the SSE endpoint.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

from app.database import SessionLocal
from app.errors.classes import SecurityError
from app.executor.credential_check import check_credentials
from app.graph.dispatcher import build_thread_id, dispatch
from app.models.workflow import WorkflowRun


async def run_workflow(
    run_id: uuid.UUID,
    workflow_definition: dict,
    mode: str,
    started_by: str,
    session_id: str | None = None,
    initial_state: dict | None = None,
) -> dict:
    """Run a workflow to completion, updating the ``workflow_run`` row.

    Args:
        run_id: Pre-allocated ``WorkflowRun.run_id``. The HTTP handler
            inserts a ``pending`` row first so the SSE stream has a
            target to subscribe to.
        workflow_definition: Canvas JSON (nodes + edges + variables).
        mode: ``"workflow"`` (single-shot) or ``"chatflow"`` (resume).
        started_by: User id who started the run. Used for the
            credential ACL pre-flight check.
        session_id: Required for ``chatflow``; ignored for ``workflow``.
        initial_state: Starting state dict. The runner injects
            ``_run_id`` and ``_workflow_variables`` before dispatch.

    Returns:
        The final state dict from the graph (in workflow mode) or the
        current paused state (in chatflow mode, when the graph hit an
        approval interrupt).

    Raises:
        SecurityError: when the credential ACL pre-flight fails.
            The ``workflow_run`` row is marked ``failed`` with
            ``error_class='security'``.
        Exception: any other exception from the graph. The row is
            marked ``failed`` with the exception's ``error_class``
            attribute (or ``'runtime'`` as default). The exception is
            re-raised.
    """
    # 1. Mark running + reserve thread_id. We do this BEFORE the
    # credential check so the row reflects the actual start of work.
    thread_id = build_thread_id(mode, session_id)
    async with SessionLocal() as session:
        run = await session.get(WorkflowRun, run_id)
        if run is None:
            raise RuntimeError(f"workflow_run {run_id} not found")
        run.status = "running"
        run.thread_id = thread_id
        await session.commit()

    # 2. Pre-flight credential ACL. Any 403 short-circuits the whole
    # run — the alternative is to fail per-node, which means a 14-node
    # workflow with a 403 on node 14 has already burned through 13 LLM
    # calls for nothing.
    try:
        await check_credentials(workflow_definition, started_by)
    except SecurityError as e:
        async with SessionLocal() as session:
            run = await session.get(WorkflowRun, run_id)
            run.status = "failed"
            run.error_class = "security"
            run.error_message = str(e)
            run.ended_at = datetime.utcnow()
            await session.commit()
        raise

    # 3. Build initial state and dispatch.
    initial_state = dict(initial_state or {})
    # ``_run_id`` is left as a UUID; the compiler json-encodes it before
    # persisting to the JSONB column. Keeping it typed here lets downstream
    # code that expects a UUID (FK relationships) work without a re-parse.
    initial_state["_run_id"] = run_id
    initial_state["_started_by"] = started_by
    initial_state["_workflow_variables"] = workflow_definition.get("variables", {})

    try:
        result = await dispatch(
            workflow_definition, mode, session_id, initial_state,
            workflow_id=str(workflow_definition.get("id", "adhoc")),
        )
    except Exception as e:
        async with SessionLocal() as session:
            run = await session.get(WorkflowRun, run_id)
            run.status = "failed"
            run.error_class = getattr(e, "error_class", "runtime")
            run.error_message = str(e)
            run.ended_at = datetime.utcnow()
            await session.commit()
        raise

    # 4. Mark completed.
    async with SessionLocal() as session:
        run = await session.get(WorkflowRun, run_id)
        run.status = "completed"
        run.ended_at = datetime.utcnow()
        await session.commit()
    return result


def schedule_run(
    workflow_definition: dict,
    mode: str,
    started_by: str,
    session_id: str | None = None,
    initial_state: dict | None = None,
) -> uuid.UUID:
    """Schedule a workflow run as a background ``asyncio.create_task``.

    Returns:
        The ``run_id`` immediately. The caller (typically a FastAPI
        endpoint) returns the ``run_id`` to the client, who can then
        ``GET /api/runs/:id/events`` to stream progress.

    Note:
        The caller is responsible for inserting the ``pending``
        ``WorkflowRun`` row BEFORE calling ``schedule_run`` so the
        SSE stream has a target.
    """
    run_id = uuid.uuid4()
    asyncio.create_task(
        run_workflow(
            run_id, workflow_definition, mode, started_by, session_id, initial_state,
        )
    )
    return run_id


__all__ = ["run_workflow", "schedule_run"]
