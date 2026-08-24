"""Tests del agente adaptativo."""
import pytest

from agent.adaptive_agent import AdaptiveAgent
from environments.chess_env import ChessboardEnvironment
from environments.stock_env import StockMarketEnvironment
from environments.travel_env import TravelEnvironment
from models import TravelRequest


def test_strategy_for_chess():
    agent = AdaptiveAgent()
    env = ChessboardEnvironment()
    trace = agent.run(env, "find_checkmate", max_iterations=5)
    assert trace.selected_strategy == "exact_search"
    assert trace.reward == 100.0


def test_strategy_for_stock():
    agent = AdaptiveAgent()
    env = StockMarketEnvironment(seed=42)
    trace = agent.run(env, "maximize_return", max_iterations=2)
    assert trace.selected_strategy == "probabilistic_risk"
    assert trace.iterations > 0


def test_strategy_for_travel():
    agent = AdaptiveAgent()
    req = TravelRequest(
        origin="Madrid", destination="París", departure_date="2026-07-15", return_date="2026-07-18"
    )
    env = TravelEnvironment(request=req)
    trace = agent.run(env, req, max_iterations=20)
    assert trace.selected_strategy == "constraint_planning"
    assert trace.reward > 0
    assert trace.final_observation is not None


def test_safety_blocks_irreversible_without_confirmation():
    from agent.safety_guard import SafetyGuard
    from config import AgentConfig
    from models import AgentAction

    guard = SafetyGuard(AgentConfig(require_confirmation_irreversible=True))
    action = AgentAction(name="book_flight", parameters={})
    check = guard.check_action(action, user_confirmed=False)
    assert not check.allowed
    assert "requires_confirmation" in check.flags


def test_safety_allows_confirmed_irreversible():
    from agent.safety_guard import SafetyGuard
    from config import AgentConfig
    from models import AgentAction

    guard = SafetyGuard(AgentConfig(require_confirmation_irreversible=True))
    action = AgentAction(name="book_flight", parameters={})
    check = guard.check_action(action, user_confirmed=True)
    assert check.allowed
