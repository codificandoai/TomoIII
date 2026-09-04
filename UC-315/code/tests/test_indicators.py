"""Tests de indicadores técnicos."""
from __future__ import annotations

import numpy as np

import technical_indicators as ti
from config import get_config


def test_sma_basic():
    prices = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = ti.sma(prices, window=3)
    assert len(result) == len(prices)
    assert abs(result.iloc[-1] - 4.0) < 1e-9


def test_rsi_range():
    prices = np.linspace(10, 20, 50)
    result = ti.rsi(prices, window=14)
    assert 0 <= result.iloc[-1] <= 100


def test_macd_returns_dict():
    prices = np.cumsum(np.random.randn(60)) + 100
    result = ti.macd(prices, 12, 26, 9)
    assert set(result.keys()) == {"macd", "signal", "histogram"}
    assert len(result["macd"]) == len(prices)


def test_extract_features():
    prices = np.cumsum(np.random.randn(100) * 0.5) + 100
    volumes = np.random.randint(1_000_000, 10_000_000, size=100)
    cfg = get_config().features
    features = ti.extract_features(prices, volumes, cfg)
    assert "rsi" in features
    assert "macd" in features
    assert 0 <= features["rsi"] <= 100
