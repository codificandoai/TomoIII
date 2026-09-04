"""Tests del evaluador de planes UC-314."""
from __future__ import annotations

from plan_evaluator import PlanEvaluator
from recursive_planner import PlanNode


def _make_simple_tree():
    root = PlanNode(id="r", goal="X", status="executable", children=[])
    root.children = [
        PlanNode(id="c1", goal="A", status="executable", depth=1),
        PlanNode(id="c2", goal="B", status="blocked", depth=1),
    ]
    return root


def test_evaluate_metrics():
    root = _make_simple_tree()
    evaluator = PlanEvaluator()
    metrics = evaluator.evaluate(root)
    assert metrics.total_nodes == 3
    assert metrics.executable_leaves == 1
    assert metrics.blocked_leaves == 1
    assert metrics.executability_ratio == 0.5
