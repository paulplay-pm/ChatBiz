"""Node Contract package — registers all 14 node types on import.

Importing this package (or any submodule) populates ``NODE_REGISTRY`` via
the ``@register`` decorator on each node's BaseModel. The workflow
compiler (Phase 5) does ``from app.nodes import NODE_REGISTRY`` to
introspect available node types when compiling canvas JSON into a
LangGraph StateGraph.

Order of registration is determined by import order. The list below is
intentionally explicit (rather than auto-discovered via pkgutil) so
``git blame`` on this file shows the full set of registered types and
new node additions are reviewed in code review.
"""
from app.nodes.agent import AgentNode
from app.nodes.approval import ApprovalNode
from app.nodes.code import CodeNode
from app.nodes.condition import ConditionNode
from app.nodes.end import EndNode
from app.nodes.extract import ExtractNode
from app.nodes.http import HTTPNode
from app.nodes.iterate import IterateNode
from app.nodes.knowledge import KnowledgeNode
from app.nodes.llm import LLMNode
from app.nodes.loop import LoopNode
from app.nodes.registry import (
    NODE_REGISTRY,
    bind_execute_fns,
    get_contract,
    list_node_types,
    register,
)
from app.nodes.start import StartNode
from app.nodes.subflow import SubflowNode
from app.nodes.variable_assign import VariableAssignNode

# Wire concrete <type>_execute functions into NODE_REGISTRY. The @register
# decorator installs a default no-op execute_fn; the real implementations
# are module-level <type>_execute functions. This must run after all 14
# node modules are imported (above) so importlib can find them.
bind_execute_fns()

__all__ = [
    "NODE_REGISTRY",
    "get_contract",
    "list_node_types",
    "register",
    # Node contract classes
    "AgentNode",
    "ApprovalNode",
    "CodeNode",
    "ConditionNode",
    "EndNode",
    "ExtractNode",
    "HTTPNode",
    "IterateNode",
    "KnowledgeNode",
    "LLMNode",
    "LoopNode",
    "StartNode",
    "SubflowNode",
    "VariableAssignNode",
]
