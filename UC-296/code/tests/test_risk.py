"""Tests del motor de riesgo."""
from __future__ import annotations

from models import MarketSnapshot, Portfolio, RiskConstraints, TechnicalSnapshot, TradingSignal
from risk import AnomalyDetector, RiskEngine, drawdown


def test_risk_blocks_low_confidence():
    engine = RiskEngine()
    signal = TradingSignal(symbol="AAPL", side="BUY", confidence=0.2, entry_price=100.0, position_fraction=0.1)
    snapshot = MarketSnapshot(symbol="AAPL", timestamp="2026-01-01T00:00:00Z", latest_price=100.0, features=TechnicalSnapshot(symbol="AAPL", timestamp="2026-01-01T00:00:00Z"))
    portfolio = Portfolio(cash=10_000.0)
    assessment = engine.assess_signal(signal, snapshot, portfolio)
    assert not assessment.allowed
    assert "low_confidence" in assessment.flags


def test_risk_allows_valid_buy():
    engine = RiskEngine()
    signal = TradingSignal(symbol="AAPL", side="BUY", confidence=0.9, entry_price=100.0, stop_loss=98.0, take_profit=104.0, position_fraction=0.1)
    snapshot = MarketSnapshot(symbol="AAPL", timestamp="2026-01-01T00:00:00Z", latest_price=100.0, features=TechnicalSnapshot(symbol="AAPL", timestamp="2026-01-01T00:00:00Z"))
    portfolio = Portfolio(cash=10_000.0)
    assessment = engine.assess_signal(signal, snapshot, portfolio)
    assert assessment.allowed
    assert assessment.max_quantity > 0


def test_anomaly_detector():
    detector = AnomalyDetector()
    snapshot = MarketSnapshot(
        symbol="AAPL",
        timestamp="2026-01-01T00:00:00Z",
        latest_price=150.0,
        features=TechnicalSnapshot(symbol="AAPL", timestamp="2026-01-01T00:00:00Z", volatility=0.01, sma_fast=100.0),
    )
    anomalies = detector.detect({"AAPL": snapshot})
    assert "AAPL" in anomalies


def test_drawdown():
    values = [100.0, 110.0, 90.0, 105.0]
    dd = drawdown(values)
    assert dd == (110.0 - 90.0) / 110.0
