"""Tests del Monitor Metacognitivo UC-313."""
from __future__ import annotations

from metacognitive_monitor import MetacognitiveMonitor
from models import Portfolio, TradingRequest
from sam import SituationalAwarenessMiddleware


def _workspace():
    sam = SituationalAwarenessMiddleware()
    request = TradingRequest(symbols=["AAPL"], ticks=[], portfolio=Portfolio(cash=100_000.0))
    return sam.build_workspace(
        request=request,
        snapshots={"AAPL": {"symbol": "AAPL", "latest_price": 150.0, "regime": "normal"}},
        signals=[{"side": "BUY", "confidence": 0.8, "agent": "technical"}],
        hypotheses=[{"name": "bullish", "confidence": 0.75, "risk_score": 0.2}],
    )


def test_evaluate_workspace():
    monitor = MetacognitiveMonitor()
    workspace = _workspace()
    meta = monitor.evaluate_workspace(workspace)
    assert "recommendation" in meta


def test_observe_internal_state():
    monitor = MetacognitiveMonitor()
    workspace = _workspace()
    report = monitor.observe_internal_state(
        workspace,
        trading_output={"status": "ok", "signals": []},
        tot_prediction={"final_prediction": {"confidence": 0.8}},
    )
    assert "verdict" in report
    assert "plasticity" in report
    assert report["verdict"] in {"PROCEED", "REVIEW", "STOP"}


def test_map_verdict_stop_on_abort():
    monitor = MetacognitiveMonitor()
    workspace = _workspace()
    meta = {"abort": True, "need_review": True}
    from cognitive_evolution_layer import PlasticityDecision
    class FakePlasticity:
        decision = PlasticityDecision.PERSIST
    assert monitor._map_verdict(meta, FakePlasticity()) == "STOP"
