"""Tests del cerebro central (CentralBrain)."""
from __future__ import annotations

from central_brain import CentralBrain
from config import get_config
from market_data import SyntheticMarketDataGenerator
from models import TradingRequest


def _make_request(symbol: str, n_ticks: int = 80):
    gen = SyntheticMarketDataGenerator(seed=42)
    ticks = gen.generate_ticks(symbol, n=n_ticks)
    return TradingRequest(symbols=[symbol], ticks=ticks)


def test_observe_creates_snapshot_and_belief():
    brain = CentralBrain(get_config())
    req = _make_request("AAPL", 80)
    snapshots = brain.observe(req)
    assert "AAPL" in snapshots
    assert brain.get_snapshot("AAPL") is not None
    assert brain.get_belief("AAPL") is not None


def test_get_context_contains_all_brain_state():
    brain = CentralBrain(get_config())
    req = _make_request("TSLA", 80)
    brain.observe(req)
    ctx = brain.get_context("TSLA")
    assert ctx["snapshot"] is not None
    assert ctx["belief"] is not None
    assert "risk_context" in ctx
    assert "price_prediction" in ctx
    assert "empirical_estimate" in ctx


def test_predict_next_price_after_observation():
    brain = CentralBrain(get_config())
    req = _make_request("AAPL", 80)
    brain.observe(req)
    pred = brain.predict_next_price("AAPL")
    assert pred["predicted_next_price"] > 0
    assert pred["symbol"] == "AAPL"


def test_learn_from_tick_updates_brain():
    brain = CentralBrain(get_config())
    gen = SyntheticMarketDataGenerator(seed=42)
    ticks = gen.generate_ticks("AAPL", n=80)
    for i in range(len(ticks) - 1):
        brain.learn_from_tick("AAPL", ticks[i].last_price, ticks[i + 1].last_price)
    assert brain.world_model._has_trained_return_model()
    pred = brain.predict_next_price("AAPL")
    assert pred["predicted_next_price"] > 0


def test_brain_state_is_serializable():
    brain = CentralBrain(get_config())
    brain.observe(_make_request("AAPL", 80))
    state = brain.to_dict()
    assert "snapshots" in state
    assert "beliefs" in state
    assert "world_model" in state
    assert "AAPL" in state["symbols"]
