"""Tests del planificador MCTS."""
from __future__ import annotations

from config import get_config
from mcts import MCTSPlanner
from models import AgentAction, WorldModelState
from world_model import TradingWorldModel


def test_mcts_returns_plan():
    config = get_config()
    world_model = TradingWorldModel(config.model)
    mcts = MCTSPlanner(world_model, config.model.mcts)
    initial_state = WorldModelState(symbol="AAPL", price=100.0, cash=10_000.0, position=0.0, portfolio_value=10_000.0)
    levels = [
        [
            AgentAction(symbol="AAPL", side="HOLD", quantity=0.0, price=100.0),
            AgentAction(symbol="AAPL", side="BUY", quantity=1.0, price=100.0),
        ]
        for _ in range(3)
    ]
    plan = mcts.search(initial_state, levels)
    assert len(plan) > 0
    assert all(isinstance(a, AgentAction) for a in plan)
