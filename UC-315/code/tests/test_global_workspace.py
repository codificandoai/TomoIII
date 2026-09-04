"""Tests del Workspace Global (GWT) UC-313."""
from __future__ import annotations

from global_workspace import GlobalWorkspace
from models import Portfolio, TradingRequest


def test_build_workspace_and_broadcast():
    gwt = GlobalWorkspace()
    request = TradingRequest(symbols=["AAPL"], ticks=[], portfolio=Portfolio(cash=100_000.0))
    workspace = gwt.build_workspace(
        request=request,
        snapshots={"AAPL": {"symbol": "AAPL", "latest_price": 150.0, "regime": "normal"}},
        signals=[{"side": "BUY", "confidence": 0.8, "agent": "technical"}],
        hypotheses=[{"name": "bullish", "confidence": 0.75, "risk_score": 0.2}],
    )
    assert workspace.selected_hypothesis is not None
    out = gwt.broadcast(workspace, persist=True)
    assert out["messages"]
    assert out["selected"] == workspace.selected_hypothesis


def test_recall_relevant():
    gwt = GlobalWorkspace()
    gwt.memory_router.store_episode("Experiencia previa con guerra de precios en Q4")
    result = gwt.recall_relevant("guerra de precios")
    assert result["intent"] == "SEMANTIC_RECALL"
