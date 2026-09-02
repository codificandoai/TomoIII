"""Tests del módulo BDI (Beliefs, Desires, Intentions) para UC-293."""
from __future__ import annotations

import pytest

from bdi import BDIBuilder, BDIStateBuilder
from config import get_config
from market_data import SyntheticMarketDataGenerator
from models import (
    AgentAction,
    BDIDesires,
    BDIIntention,
    CandidateStrategy,
    Portfolio,
    TradingRequest,
)
from perception import MarketPerceptionPipeline


@pytest.fixture
def snapshot_and_request():
    cfg = get_config()
    gen = SyntheticMarketDataGenerator(cfg.market, seed=42)
    ticks = gen.generate_ticks("AAPL", n=80)
    pipeline = MarketPerceptionPipeline(cfg.market, cfg.features)
    snapshots = pipeline.perceive("test", {"AAPL": ticks}, news=[])
    request = TradingRequest(
        symbols=["AAPL"],
        ticks=ticks,
        portfolio=Portfolio(cash=100_000.0),
    )
    return snapshots["AAPL"], request


def test_build_beliefs(snapshot_and_request):
    snapshot, request = snapshot_and_request
    beliefs = BDIBuilder.build_beliefs(
        symbol="AAPL",
        snapshot=snapshot,
        portfolio_cash=request.portfolio.cash,
        portfolio_position=0.0,
        world_model=None,
        cost_basis=120.0,
    )
    assert beliefs.symbol == "AAPL"
    assert beliefs.current_price > 0
    assert beliefs.cost_basis == 120.0
    assert beliefs.latest_features is not None


def test_build_desires(snapshot_and_request):
    snapshot, request = snapshot_and_request
    desires = BDIBuilder.build_desires(request, request.constraints)
    assert desires.primary_goal
    assert desires.max_position_pct > 0


def test_build_intention():
    strategy = CandidateStrategy(
        name="test_strategy",
        actions=[AgentAction(symbol="AAPL", side="BUY", quantity=10, price=150.0, confidence=0.8)],
    )
    intention = BDIBuilder.build_intention(strategy, justification="test")
    assert intention.planned_action == "BUY"
    assert intention.justification == "test"
    assert intention.status == "draft"


def test_build_cot_trace():
    signals = [
        {"agent": "technical", "side": "BUY", "confidence": 0.8, "entry_price": 150.0, "stop_loss": 145.0, "take_profit": 160.0},
    ]
    evaluations = [{"final_score": 0.9, "expected_return": 0.05, "risk_score": 0.1}]
    selected = {"name": "best", "actions": [AgentAction(symbol="AAPL", side="BUY", quantity=10, price=150.0).to_dict()]}
    trace = BDIBuilder.build_cot_trace(signals, evaluations, selected)
    assert len(trace) == 3
    assert trace[0].thought


def test_bdi_state_builder(snapshot_and_request):
    snapshot, request = snapshot_and_request
    beliefs = BDIBuilder.build_beliefs("AAPL", snapshot, 100_000.0, 0.0)
    desires = BDIDesires()
    intention = BDIIntention()
    state = BDIStateBuilder.build(beliefs, desires, draft=intention)
    assert state.bdi_state_id
    assert state.beliefs
    assert state.desires
    assert state.draft_intention is not None
