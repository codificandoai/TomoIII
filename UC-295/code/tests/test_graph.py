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
