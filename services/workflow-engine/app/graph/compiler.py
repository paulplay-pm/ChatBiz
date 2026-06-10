"""Compile a workflow_definition dict into a LangGraph CompiledStateGraph.

Pure function (same input -> same output) with an in-memory compile cache.

The compiler drives the workflow-state-machine spec
(``openspec/changes/implement-workflow-engine/specs/workflow-state-machine``):

- Reads ``workflow_definition`` (canvas JSON: nodes + edges + variables).
- Looks up each node's type in ``NODE_REGISTRY`` (raises
  ``NodeTypeNotRegisteredError`` for unknown types).
- Wraps the concrete ``<type>_execute`` function with audit-trail scaffolding
  (``write_node_event`` for running / completed / failed transitions).
- Builds a LangGraph ``StateGraph`` (state schema = ``dict``) with the
  workflow's edges + conditional edges.
- Caches the compiled graph by ``(workflow_id, version)`` so repeated
  ``dispatch()`` calls for the same definition don't pay the re-compile cost.

Cache invalidation lives in ``clear_compile_cache()``: the workflow
definition PUT endpoint calls this on every save so a stale compiled
graph never serves a new definition.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from langgraph.graph import END, StateGraph

from app.errors.classes import (
    NodeTypeNotRegisteredError,
    UserError,
)
from app.executor.node_event import write_node_event
from app.nodes.registry import NODE_REGISTRY

# In-memory cache: key = "<workflow_id>:<version>", value = CompiledStateGraph.
# This is per-process; multi-instance deployments get a cache per replica,
# which is fine because compile cost is small (~ms).
_cache: dict[str, Any] = {}


def compile_state_graph(workflow_definition: dict, workflow_id: str = "adhoc") -> Any:
    """Compile a ``workflow_definition`` dict into a LangGraph CompiledStateGraph.

    Args:
        workflow_definition: Canvas JSON, shape::

            {
              "nodes": [{"id": "n1", "type": "start", "config": {...}, "position": {...}}, ...],
              "edges": [{"from": "n1", "to": "n2", "condition": "..."}],
              "variables": {"key": "value"}
            }

        workflow_id: Used as part of the cache key. Defaults to ``"adhoc"`` for
            ad-hoc / debug compiles.

    Returns:
        A LangGraph ``CompiledStateGraph`` ready for ``ainvoke`` / ``astream``.

    Raises:
        ValueError: when ``nodes`` is empty.
        NodeTypeNotRegisteredError: when a node references an unknown type.
    """
    cache_key = f"{workflow_id}:{workflow_definition.get('version', 0)}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    graph: StateGraph = StateGraph(dict)
    nodes = workflow_definition.get("nodes", [])
    edges = workflow_definition.get("edges", [])

    if not nodes:
        raise ValueError("workflow_definition must have at least one node")

    # Add all nodes. ``_make_node_fn`` produces the wrapped function that
    # runs ``execute_fn`` and writes a ``node_event`` row on every transition.
    for n in nodes:
        type_name = n["type"]
        if type_name not in NODE_REGISTRY:
            raise NodeTypeNotRegisteredError(
                f"节点类型 {type_name!r} 未注册。已注册: {sorted(NODE_REGISTRY)}"
            )
        graph.add_node(n["id"], _make_node_fn(n))

    # Set entry point: first node in the list.
    graph.set_entry_point(nodes[0]["id"])

    # Add edges. Conditional edges use a router function that returns either
    # the target node id or the default node id (or ``END``).
    for e in edges:
        if "condition" in e:
            target = e["to"]
            default = e.get("default") or END
            # The path_map must include both branches; LangGraph uses the
            # router's return value to look up the next node.
            graph.add_conditional_edges(
                e["from"],
                _make_router(e["condition"], target, default),
                {target: target, default: default},
            )
        else:
            graph.add_edge(e["from"], e["to"])

    compiled = graph.compile()
    _cache[cache_key] = compiled
    return compiled


def _make_router(expression: str, target: str, default: str):
    """Build a LangGraph conditional-edge router from a Jinja2 boolean expression.

    The router returns ``target`` if the expression renders truthy, otherwise
    ``default``. ``evaluate_condition`` keeps the truthy/falsy semantics in
    one place (see ``app/graph/conditional.py``).
    """
    from app.graph.conditional import evaluate_condition

    async def router(state: dict) -> str:
        if evaluate_condition(expression, state):
            return target
        return default

    return router


def _make_node_fn(node_def: dict):
    """Build a LangGraph node function for one node in the workflow.

    Wraps ``NODE_REGISTRY[type].execute_fn`` with:

    1. ``write_node_event("running")`` at the start.
    2. ``validate_config`` on the raw ``config`` dict from the workflow definition.
    3. The actual ``execute_fn`` call, returning its output dict.
    4. ``write_node_event("completed")`` on success.
    5. ``write_node_event("failed")`` on any exception, then re-raise so the
       workflow runner (Task 6.1) can mark the whole run as failed.
    """
    node_id = node_def["id"]
    node_type = node_def["type"]
    node_config = node_def.get("config", {})

    async def node_fn(state: dict) -> dict:
        run_id = state.get("_run_id")
        started_at = datetime.utcnow()
        # Write the "running" event first so partial progress is observable
        # in the SSE stream even if the node crashes hard.
        await write_node_event(run_id, node_id, "running", input_json=state)

        try:
            contract = NODE_REGISTRY[node_type]
            config = contract.validate_config(node_config)
            # Inputs default to the full state dict; downstream nodes can
            # read upstream outputs via ``state["node_outputs"]``.
            inputs = state.get("node_inputs", state)
            outputs = await contract.execute_fn(config, inputs)
            await write_node_event(
                run_id, node_id, "completed",
                input_json=state, output_json=outputs, started_at=started_at,
            )
            return {**state, "node_outputs": outputs, "_last_node_id": node_id}
        except UserError as e:
            # User errors are boundary #3: do not retry.
            await write_node_event(
                run_id, node_id, "failed",
                input_json=state, error_class="user", error_message=str(e),
                started_at=started_at,
            )
            raise
        except Exception as e:
            error_class = getattr(e, "error_class", "runtime")
            await write_node_event(
                run_id, node_id, "failed",
                input_json=state, error_class=error_class, error_message=str(e),
                started_at=started_at,
            )
            raise

    return node_fn


def clear_compile_cache() -> None:
    """Clear the compiled graph cache.

    Call this on ``PUT /api/workflows/:id`` so a re-saved definition is
    recompiled on the next ``dispatch()`` call. The cache is also cleared
    by tests via the ``--clear-cache`` test fixture.
    """
    _cache.clear()


__all__ = ["compile_state_graph", "clear_compile_cache"]
