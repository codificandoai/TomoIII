"""Tests del simulador Monte Carlo."""
from __future__ import annotations

from config import get_config
from models import AgentAction, TradingRequest, WorldModelState
from simulator import MonteCarloSimulator
from world_model import TradingWorldModel


def test_simulate_strategy():
    config = get_config()
    wm = TradingWorldModel(config.model)
    sim = MonteCarloSimulator(wm, config.model)
    actions = [AgentAction(symbol="AAPL", side="BUY", quantity=5.0, price=100.0)]
    initial_state = WorldModelState(symbol="AAPL", price=100.0, cash=10_000.0, position=0.0, portfolio_value=10_000.0)
    request = TradingRequest(symbols=["AAPL"])
    candidate = sim.simulate_strategy("s1", actions, initial_state, request)
    assert candidate.strategy_id == "s1"
    assert candidate.expected_return is not None
