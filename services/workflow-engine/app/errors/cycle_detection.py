"""DAG cycle detection using NetworkX."""
import networkx as nx
from typing import Optional


def detect_cycle(workflow_definition: dict) -> Optional[list]:
    """Return a list of (from, to) edges that form a cycle, or None if acyclic."""
    g = nx.DiGraph()
    for n in workflow_definition.get("nodes", []):
        g.add_node(n["id"])
    for e in workflow_definition.get("edges", []):
        g.add_edge(e["from"], e["to"])
    try:
        return list(nx.find_cycle(g))
    except nx.NetworkXNoCycle:
        return None
