"""Node Contract registry: Pydantic BaseModel → LangGraph node function + I/O schema + UI schema.

This module implements the single source of truth for node types (eng-review Arch #2 +
Quality #1): one Pydantic BaseModel per node type drives 4 products at runtime:

1. **UI config schema** — exposed via ``GET /api/nodes/:type/schema`` and consumed by
   the canvas frontend to render the config form.
2. **LangGraph node function** — ``wrap_for_langgraph()`` returns an async callable
   that reads ``state["node_config"]`` + ``state["node_inputs"]`` and returns
   ``state["node_outputs"]``.
3. **I/O JSON schema** — derived from the BaseModel via ``model_json_schema()``.
4. **Validation** — ``validate_config()`` runs ``model_validate()`` on raw config dicts
   from canvas save / workflow definition load.

The registry is a module-level dict populated at import time by the ``@register``
decorator on each node module (e.g. ``app/nodes/llm.py``). All 14 node types MUST
be importable from ``app.nodes`` so the workflow compiler can introspect them.
"""
from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel

from app.errors.classes import NodeOutputValidationError, NodeTypeNotRegisteredError

NODE_REGISTRY: dict[str, "NodeContract"] = {}


class NodeContract:
    """One Node Contract entry. Wraps a Pydantic BaseModel + execute() async function.

    Drives 4 products at runtime: (1) UI config schema, (2) LangGraph node function,
    (3) I/O JSON schema, (4) validation.
    """

    def __init__(
        self,
        type_name: str,
        base_model: type[BaseModel],
        execute_fn: Callable,
        version: str = "1.0.0",
    ) -> None:
        self.type_name = type_name
        self.base_model = base_model
        self.execute_fn = execute_fn
        self.version = version
        NODE_REGISTRY[type_name] = self

    def schema(self) -> dict:
        """Return JSON schema for this node's config + I/O. Used by GET /api/nodes/:type/schema."""
        return {
            "type": self.type_name,
            "version": self.version,
            "config_schema": self.base_model.model_json_schema(),
        }

    def validate_config(self, config: dict) -> BaseModel:
        """Validate raw config dict against the BaseModel. Raises pydantic.ValidationError on failure."""
        return self.base_model.model_validate(config)

    def wrap_for_langgraph(self) -> Callable:
        """Wrap execute_fn as a LangGraph node function.

        Reads ``state["node_config"]`` + ``state["node_inputs"]``, returns state updates.
        The output is merged into state under the key ``"node_outputs"`` — LangGraph
        uses this to thread the node's results into the next node's input mapping.
        """
        contract = self

        async def node_fn(state: dict) -> dict:
            config = state.get("node_config", {})
            inputs = state.get("node_inputs", {})
            try:
                outputs = await contract.execute_fn(config, inputs)
            except Exception:
                # Re-raise so LangGraph can record node failure upstream
                # (the workflow runner wraps each node in a try/except that
                # writes a NodeEvent row and surfaces the error to the caller).
                raise
            if not isinstance(outputs, dict):
                raise NodeOutputValidationError(
                    f"节点 {contract.type_name} 输出必须是 dict,实际为 {type(outputs).__name__}"
                )
            return {**state, "node_outputs": outputs}

        return node_fn


def register(type_name: str, version: str = "1.0.0"):
    """Decorator to register a node type. Usage:

        @register("start", version="1.0.0")
        class StartNode(BaseNode):
            config: StartConfig

    The decorator also installs a default ``execute_fn`` that returns ``{}``. Real
    implementations should override it by calling ``NodeContract.wrap_for_langgraph()``
    on the registry entry, or by passing a custom ``execute_fn`` to ``NodeContract``
    directly. For MVP, we keep the decorator-side wiring simple: the node module
    defines an ``<type>_execute(config, inputs) -> dict`` async function, and the
    workflow compiler picks it up via convention (see ``app/graph/compiler.py``).
    """

    def deco(cls: type[BaseModel]):
        async def default_execute(config, inputs):
            return {}

        NODE_REGISTRY[type_name] = NodeContract(type_name, cls, default_execute, version)
        return cls

    return deco


def get_contract(type_name: str) -> NodeContract:
    """Look up a node contract by type name. Raises ``NodeTypeNotRegisteredError`` if missing."""
    if type_name not in NODE_REGISTRY:
        raise NodeTypeNotRegisteredError(
            f"节点类型 {type_name!r} 未注册;已注册类型: {sorted(NODE_REGISTRY)}"
        )
    return NODE_REGISTRY[type_name]


def list_node_types() -> list[dict]:
    """List all registered node types. Used by the canvas frontend to render the node panel."""
    return [
        {
            "type": c.type_name,
            "version": c.version,
            "config_schema": c.base_model.model_json_schema(),
        }
        for c in NODE_REGISTRY.values()
    ]


__all__ = [
    "NODE_REGISTRY",
    "NodeContract",
    "register",
    "get_contract",
    "list_node_types",
]
