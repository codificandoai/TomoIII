"""Tests de Juice Agents validators."""
from __future__ import annotations

from config import JuiceConfig, get_config
from juice_agents import JuiceTechnicalAgent, JuiceValidator
from models import MarketSnapshot, TechnicalSnapshot, TradingSignal


def test_technical_agent_scores_buy_with_oversold_rsi():
    agent = JuiceTechnicalAgent()
    signal = TradingSignal(symbol="AAPL", side="BUY", confidence=0.7, entry_price=100.0)
    snapshot = MarketSnapshot(
        symbol="AAPL",
        timestamp="2026-01-01T00:00:00Z",
        latest_price=100.0,
        features=TechnicalSnapshot(symbol="AAPL", timestamp="2026-01-01T00:00:00Z", rsi=25.0, trend_direction=1, volatility=0.01),
    )
    result = agent.validate(signal, snapshot)
    assert 0 <= result["score"] <= 1


def test_validator_returns_result():
    config = JuiceConfig(enabled=False)
    validator = JuiceValidator(config)
    signal = TradingSignal(symbol="AAPL", side="BUY", confidence=0.8, entry_price=100.0, stop_loss=98.0, take_profit=104.0, position_fraction=0.05)
    snapshot = MarketSnapshot(
        symbol="AAPL",
        timestamp="2026-01-01T00:00:00Z",
        latest_price=100.0,
        features=TechnicalSnapshot(symbol="AAPL", timestamp="2026-01-01T00:00:00Z", rsi=45.0, trend_direction=1, volatility=0.01),
    )
    result = validator.validate(signal, snapshot)
    assert result.consensus_score >= 0
    assert result.validation_id
