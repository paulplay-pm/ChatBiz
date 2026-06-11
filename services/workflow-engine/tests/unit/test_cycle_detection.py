"""Unit tests for app/errors/cycle_detection.py — DAG cycle detection via NetworkX."""
from app.errors.cycle_detection import detect_cycle


def test_empty_graph_no_cycle():
    assert detect_cycle({"nodes": [], "edges": []}) is None


def test_single_node_no_cycle():
    assert detect_cycle({"nodes": [{"id": "A"}], "edges": []}) is None


def test_sequential_dag_no_cycle():
    assert detect_cycle(
        {"nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}], "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}]},
    ) is None


def test_simple_two_node_cycle():
    result = detect_cycle(
        {"nodes": [{"id": "A"}, {"id": "B"}], "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "A"}]},
    )
    assert result is not None
    edges = set(result)
    assert ("A", "B") in edges or ("B", "A") in edges


def test_three_node_cycle():
    result = detect_cycle(
        {"nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}], "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}, {"from": "C", "to": "A"}]},
    )
    assert result is not None
    assert len(result) == 3


def test_self_loop():
    result = detect_cycle({"nodes": [{"id": "A"}], "edges": [{"from": "A", "to": "A"}]})
    assert result is not None
    assert result == [("A", "A")]


def test_multibranch_dag():
    assert detect_cycle(
        {"nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}, {"id": "D"}], "edges": [{"from": "A", "to": "B"}, {"from": "A", "to": "C"}, {"from": "B", "to": "D"}, {"from": "C", "to": "D"}]},
    ) is None


def test_cycle_in_subgraph():
    result = detect_cycle(
        {"nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}, {"id": "D"}], "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}, {"from": "C", "to": "B"}, {"from": "C", "to": "D"}]},
    )
    assert result is not None
