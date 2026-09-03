"""Tests del exchange simulado."""
from __future__ import annotations

from exchange import ExchangeSimulator
from models import AgentAction, Portfolio


def test_buy_reduces_cash():
    ex = ExchangeSimulator()
    portfolio = Portfolio(cash=10_000.0)
    action = AgentAction(symbol="AAPL", side="BUY", quantity=10.0, price=100.0)
    result = ex.submit_order(action, portfolio, price=100.0)
    assert result.status == "FILLED"
    assert result.remaining_cash < 10_000.0
    assert result.remaining_position == 10.0


def test_sell_requires_shares():
    ex = ExchangeSimulator()
    portfolio = Portfolio(cash=10_000.0, positions={"AAPL": 5.0})
    action = AgentAction(symbol="AAPL", side="SELL", quantity=10.0, price=100.0)
    result = ex.submit_order(action, portfolio, price=100.0)
    assert result.status == "REJECTED"


def test_hold_is_free():
    ex = ExchangeSimulator()
    portfolio = Portfolio(cash=10_000.0)
    action = AgentAction(symbol="AAPL", side="HOLD", quantity=0.0, price=100.0)
    result = ex.submit_order(action, portfolio, price=100.0)
    assert result.status == "FILLED"
    assert result.remaining_cash == 10_000.0
