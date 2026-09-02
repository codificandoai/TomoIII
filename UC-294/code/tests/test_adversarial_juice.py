"""Tests del filtro adversarial Confrontational Juice para UC-293."""
from __future__ import annotations

import pytest

from adversarial_juice import ConfrontationalJuice
from models import AgentAction, BDIBeliefs, BDIDesires, BDIIntention


@pytest.fixture
def juice():
    return ConfrontationalJuice()


@pytest.fixture
def base_beliefs():
    return BDIBeliefs(
        symbol="AAPL",
        current_price=150.0,
        predicted_next_price=151.5,
        rsi=50.0,
        trend_direction=1,
        news_sentiment=0.2,
        volatility=0.01,
        world_model_uncertainty=0.1,
        portfolio_cash=100_000.0,
        portfolio_position=0.0,
    )


@pytest.fixture
def base_desires():
    return BDIDesires(min_signal_confidence=0.5, max_position_pct=0.2)


def test_approved_valid_buy(juice, base_beliefs, base_desires):
    intention = BDIIntention(
        planned_action="BUY",
        actions=[AgentAction(symbol="AAPL", side="BUY", quantity=10, price=150.0, confidence=0.8, stop_loss=145.0, take_profit=160.0)],
        justification="buy valid",
    )
    verdict = juice.confront(base_beliefs, base_desires, intention)
    assert verdict.approved is True
    assert verdict.survival_score >= 80
    assert not verdict.issues


def test_rejected_buy_contra_trend(juice, base_beliefs, base_desires):
    beliefs = base_beliefs.model_copy(update={"trend_direction": -1})
    intention = BDIIntention(
        planned_action="BUY",
        actions=[AgentAction(symbol="AAPL", side="BUY", quantity=10, price=150.0, confidence=0.8, stop_loss=145.0, take_profit=160.0)],
    )
    verdict = juice.confront(beliefs, base_desires, intention)
    assert verdict.approved is False
    assert any("tendencia" in issue.lower() for issue in verdict.issues)


def test_rejected_sell_in_oversold(juice, base_beliefs, base_desires):
    beliefs = base_beliefs.model_copy(update={"rsi": 25.0, "trend_direction": 1})
    intention = BDIIntention(
        planned_action="SELL",
        actions=[AgentAction(symbol="AAPL", side="SELL", quantity=10, price=150.0, confidence=0.8, stop_loss=155.0, take_profit=140.0)],
    )
    verdict = juice.confront(beliefs, base_desires, intention)
    assert verdict.approved is False
    assert any("rsi" in issue.lower() for issue in verdict.issues)


def test_distilled_low_confidence(juice, base_beliefs, base_desires):
    intention = BDIIntention(
        planned_action="BUY",
        actions=[AgentAction(symbol="AAPL", side="BUY", quantity=100, price=150.0, confidence=0.3, stop_loss=145.0, take_profit=160.0)],
    )
    verdict = juice.confront(base_beliefs, base_desires, intention)
    assert not verdict.approved
    assert verdict.survival_score > 0
    corrected = verdict.corrected_intention
    assert corrected["planned_action"] == "HOLD" or corrected["planned_action"] == "BUY"


def test_rejected_high_uncertainty(juice, base_beliefs, base_desires):
    beliefs = base_beliefs.model_copy(update={"world_model_uncertainty": 0.9})
    intention = BDIIntention(
        planned_action="BUY",
        actions=[AgentAction(symbol="AAPL", side="BUY", quantity=10, price=150.0, confidence=0.8, stop_loss=145.0, take_profit=160.0)],
    )
    verdict = juice.confront(beliefs, base_desires, intention)
    assert not verdict.approved
    assert any("incertidumbre" in issue.lower() for issue in verdict.issues)


def test_hold_neutral_is_approved(juice, base_beliefs, base_desires):
    intention = BDIIntention(planned_action="HOLD", actions=[], justification="neutral")
    verdict = juice.confront(base_beliefs, base_desires, intention)
    assert verdict.approved is True
    assert verdict.survival_score == 100.0
