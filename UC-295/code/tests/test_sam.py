"""Tests del Situational Awareness Middleware (SAM) para UC-294."""
from __future__ import annotations

import pytest

from models import Portfolio, TradingRequest
from sam import (
    Envelope,
    MetacognitionModule,
    SafetySupervisor,
    SituationalAwarenessMiddleware,
)


@pytest.fixture
def sam():
    return SituationalAwarenessMiddleware(agent_identity="UC294.Test", max_memory_items=5)


@pytest.fixture
def base_request():
    return TradingRequest(
        symbols=["AAPL"],
        ticks=[],
        portfolio=Portfolio(cash=100_000.0),
    )


def test_store_episode_limits_memory(sam):
    for i in range(10):
        sam.store_episode("PERCEPTION", f"event {i}")
    assert len(sam.working_memory) == sam.max_memory_items
    assert sam.working_memory[0].content == "event 5"


def test_metacognition_lowers_confidence_after_errors(sam):
    sam.store_episode("ACTION", "Orden ejecutada")
    sam.store_episode("OBSERVATION", "ERROR: slippage alto")
    sam.store_episode("OBSERVATION", "ERROR: orden rechazada")
    assert sam.self_model.recent_errors == 2
    assert sam.self_model.confidence_level <= 0.8
    assert sam.self_model.cognitive_load == "HIGH"


def test_build_workspace_with_alerts(sam, base_request):
    snapshots = {
        "AAPL": {
            "symbol": "AAPL",
            "latest_price": 150.0,
            "features": {"volatility": 0.06, "rsi": 70.0},
            "regime": "high_volatility",
        }
    }
    workspace = sam.build_workspace(
        base_request,
        snapshots,
        signals=[{"side": "BUY", "confidence": 0.8, "agent": "technical"}],
        alerts=["API degradada"],
        hypotheses=[{"name": "buy_dip", "confidence": 0.8, "risk_score": 0.2}],
    )
    # Sin ticks, la calidad de datos es nula y la API se marca como degradada
    assert workspace.environment["api_health"] == "DEGRADED"
    assert workspace.environment["market_volatility"] == "HIGH"
    assert "high_volatility" in workspace.broadcast["flags"]
    assert workspace.selected_hypothesis is not None


def test_metacognition_detects_low_confidence(sam, base_request):
    sam.self_model.confidence_level = 0.2
    snapshots = {
        "AAPL": {
            "symbol": "AAPL",
            "latest_price": 150.0,
            "features": {"volatility": 0.01},
            "regime": "ranging",
        }
    }
    workspace = sam.build_workspace(base_request, snapshots, signals=[])
    meta = MetacognitionModule().evaluate(workspace)
    assert meta["need_review"] is True
    assert any("baja_confianza_self" in issue for issue in meta["issues"])


def test_metacognition_detects_signal_conflict(sam, base_request):
    snapshots = {
        "AAPL": {
            "symbol": "AAPL",
            "latest_price": 150.0,
            "features": {"volatility": 0.01},
            "regime": "ranging",
        }
    }
    workspace = sam.build_workspace(
        base_request,
        snapshots,
        signals=[{"side": "BUY", "confidence": 0.9}, {"side": "SELL", "confidence": 0.9}],
    )
    meta = MetacognitionModule().evaluate(workspace)
    assert "conflicto_senales_buy_sell" in meta["issues"]


def test_safety_blocks_missing_stop_loss():
    strategy = {
        "actions": [
            {
                "symbol": "AAPL",
                "side": "BUY",
                "quantity": 100,
                "price": 150.0,
                "confidence": 0.9,
            }
        ]
    }
    request = TradingRequest(
        symbols=["AAPL"],
        ticks=[],
        portfolio=Portfolio(cash=100_000.0),
    )
    snapshots = {"AAPL": {"latest_price": 150.0, "features": {}}}
    result = SafetySupervisor().check(strategy, request, snapshots)
    assert result["allowed"] is False
    assert "stop_loss_missing" in result["issues"]
    assert result["rollback"]["action"] == "REVERT_TO_HOLD"


def test_envelope_pack_unpack():
    payload = {"x": 1}
    env = Envelope().pack("a", "b", "test", payload, {"meta": "data"})
    assert env["source"] == "a"
    assert env["destination"] == "b"
    assert Envelope().unpack(env) == payload
