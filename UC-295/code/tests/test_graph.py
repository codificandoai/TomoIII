"""Tests de integración del grafo LangGraph."""
from __future__ import annotations

from graph import run_agent
from market_data import SyntheticMarketDataGenerator
from models import Portfolio, TradingRequest


def test_run_agent_returns_final_output():
    gen = SyntheticMarketDataGenerator(seed=42)
    ticks = gen.generate_ticks("AAPL", n=100)
    request = TradingRequest(
        symbols=["AAPL"],
        ticks=ticks,
        portfolio=Portfolio(cash=100_000.0),
    )
    final_state = run_agent(request, recursion_limit=50)
    assert "final_output" in final_state
    output = final_state["final_output"]
    assert output["status"] in ("done", "awaiting_confirmation", "blocked")


def test_run_agent_includes_tot_prediction_node():
    gen = SyntheticMarketDataGenerator(seed=42)
    ticks = gen.generate_ticks("AAPL", n=80)
    request = TradingRequest(
        symbols=["AAPL"],
        ticks=ticks,
        portfolio=Portfolio(cash=100_000.0),
    )
    final_state = run_agent(request, recursion_limit=50)
    output = final_state.get("final_output", {})
    assert "tot_prediction" in output
    assert "AAPL" in (output["tot_prediction"] or {})
    aapl = output["tot_prediction"]["AAPL"]
    assert "final_prediction" in aapl
    assert aapl["final_prediction"]["predicted_ask"] > aapl["final_prediction"]["predicted_bid"] > 0.0
