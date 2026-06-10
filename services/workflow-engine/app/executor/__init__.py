"""Workflow execution engine: runner, retry, node_event writer, credential pre-flight, SSE.

The execution engine is the runtime counterpart to the workflow compiler
(``app/graph/``). The compiler turns canvas JSON into a LangGraph
``CompiledStateGraph``; the executor runs that graph against a real
``workflow_run`` row, persisting every node transition as a
``node_event`` row and streaming those events to SSE clients.

Layered as:

- ``runner.py`` — entry point: ``run_workflow`` (long-running) and
  ``schedule_run`` (fire-and-forget via ``asyncio.create_task``).
- ``retry.py`` — 1x indexed-backoff retry helper for runtime errors
  (no retry for user / security errors per the 4-boundary model).
- ``node_event.py`` — ``write_node_event`` row writer used by both
  the compiler (per-node events) and the runner (run-level events).
- ``credential_check.py`` — pre-flight ACL check for all
  ``credential_id`` references in a workflow definition.
- ``sse.py`` — ``run_events_sse`` async generator for the
  ``GET /api/runs/:id/events`` endpoint.
"""
