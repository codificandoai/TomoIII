"""Tests del 'cerebro' del world model: predicción de ticks y retroalimentación."""
from __future__ import annotations

import numpy as np

from config import get_config
from market_data import SyntheticMarketDataGenerator
from models import AgentAction, TradingRequest, WorldModelState
from world_model import TradingWorldModel


def test_predict_next_price_before_training_uses_empirical_return():
    wm = TradingWorldModel(get_config().model)
    wm.update_price_history("AAPL", 100.0)
    wm.update_price_history("AAPL", 101.0)
    pred = wm.predict_next_price("AAPL", current_price=101.0)
    assert pred["predicted_next_price"] > 0
    assert pred["model_type"] == "neural"
    assert pred["uncertainty"] >= 0.9  # sin entrenar, alta incertidumbre


def test_update_from_tick_trains_return_model():
    wm = TradingWorldModel(get_config().model)
    gen = SyntheticMarketDataGenerator(seed=42)
    ticks = gen.generate_ticks("AAPL", n=80)

    # Retroalimentar con pares de ticks reales
    for i in range(len(ticks) - 1):
        wm.update_from_tick(
            symbol="AAPL",
            current_price=ticks[i].last_price,
            next_price=ticks[i + 1].last_price,
        )

    assert wm._has_trained_return_model()
    pred = wm.predict_next_price("AAPL", current_price=ticks[-1].last_price)
    assert pred["predicted_next_price"] > 0


def test_predicted_prices_are_reasonable_after_training():
    """El modelo entrenado produce predicciones de ticks dentro de un rango razonable."""
    cfg = get_config()
    wm = TradingWorldModel(cfg.model)
    gen = SyntheticMarketDataGenerator(seed=123)
    ticks = gen.generate_ticks("AAPL", n=200)

    # Fase 1: predicciones iniciales (sin entrenar)
    initial_preds = []
    for i in range(50, 100):
        pred = wm.predict_next_price("AAPL", current_price=ticks[i].last_price)
        initial_preds.append(pred["predicted_next_price"])

    # Fase 2: entrenar con pares de ticks
    for i in range(len(ticks) - 1):
        wm.update_from_tick(
            "AAPL",
            current_price=ticks[i].last_price,
            next_price=ticks[i + 1].last_price,
        )

    # Fase 3: predicciones posteriores
    final_preds = []
    for i in range(170, 199):
        pred = wm.predict_next_price("AAPL", current_price=ticks[i].last_price)
        final_preds.append(pred["predicted_next_price"])

    assert wm._has_trained_return_model()
    assert len(final_preds) > 0
    # Las predicciones deben ser positivas y no desviarse más de 20% del precio actual
    for current, pred in zip(ticks[170:199], final_preds):
        assert 0 < pred < current.last_price * 1.2
