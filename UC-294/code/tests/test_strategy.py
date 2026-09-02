"""Tests del generador de estrategias y del crítico."""
from __future__ import annotations

from config import get_config
from critic import StrategyCritic
from models import AgentAction, CandidateStrategy
from planner import StrategyGenerator
from world_model import TradingWorldModel


def test_strategy_generator_returns_candidates():
    config = get_config()
    wm = TradingWorldModel(config.model)
    generator = StrategyGenerator(wm, config.model)
    from models import TradingRequest
    request = TradingRequest(symbols=["AAPL"], risk_tolerance="moderate", mode="paper")
    snapshots = {
        "AAPL": {
            "latest_price": 100.0,
            "features": {"latest_price": 100.0, "volatility": 0.01},
            "regime": "trending_bullish",
        }
    }
    portfolio = {"cash": 100_000.0, "positions": {}}
    actions, meta = generator.generate(request, snapshots, portfolio)
    assert len(actions) > 0
    assert meta["generated"] == len(actions)


def test_critic_selects_best():
    config = get_config()
    candidates = [
        CandidateStrategy(name="hold", actions=[AgentAction(symbol="AAPL", side="HOLD")], expected_return=0.0, expected_risk=0.0, risk_score=0.0, final_score=0.0),
        CandidateStrategy(name="buy", actions=[AgentAction(symbol="AAPL", side="BUY", quantity=10.0, price=100.0)], expected_return=1.0, expected_risk=0.5, risk_score=0.1, final_score=0.0),
    ]
    critic = StrategyCritic(config.model)
    best = critic.select_best(candidates)
    assert best is not None
    assert best.final_score >= 0
