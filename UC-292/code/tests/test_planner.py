"""Tests de compatibilidad del módulo planner.py (strategy generator)."""
from __future__ import annotations

from planner import StrategyGenerator, candidate_to_strategy


def test_candidate_to_strategy():
    from models import AgentAction
    action = AgentAction(symbol="AAPL", side="BUY", quantity=10.0, price=100.0)
    strategy = candidate_to_strategy([action], name="test")
    assert strategy.name == "test"
    assert strategy.actions[0].side == "BUY"
