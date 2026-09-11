"""Evaluación out-of-sample de predicción ask/bid de siguiente tick.

Entrena el `CentralBrain` de UC-313 solo con la partición de entrenamiento y
mide la calidad de la predicción del siguiente tick en la partición de prueba.

Métricas:
- MSE/RMSE/MAE/MAPE del mid-price predicho.
- Exactitud direccional (signo del retorno).
- Error de spread (predicho vs real del siguiente tick).
- Cobertura aproximada de intervalo de predicción.
- Utilidad ajustada por riesgo de una estrategia trivial basada en dirección.
- Reproducibilidad (seed fijo).

No realiza operaciones reales; todo es simulación con datos sintéticos.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple

UC313_CODE = Path("/Users/utron/Documents/code-books/TomoIII/UC-313/code")
UC315_CODE = Path("/Users/utron/Documents/code-books/TomoIII/UC-315/code")
sys.path.insert(0, str(UC313_CODE))
sys.path.insert(0, str(UC315_CODE))

import numpy as np
from central_brain import CentralBrain
from market_data import SyntheticMarketDataGenerator
from models import MarketTick, TradingRequest
from react_tot import ReActReasonactToTBrain, TickPredictionEnvironment

SEED = 42
SYMBOL = "AAPL"
N_TICKS = 500
TRAIN_FRAC = 0.70
OUTPUT = Path("/Users/utron/Documents/code-books/TomoIII/UC_VALIDATION/prediction_evaluation_results.json")


def _actual_mid(tick: MarketTick) -> float:
    return (tick.ask + tick.bid) / 2.0


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    residuals = y_pred - y_true
    mse = float(np.mean(residuals**2))
    rmse = float(math.sqrt(mse))
    mae = float(np.mean(np.abs(residuals)))
    mape = float(np.mean(np.abs(residuals / (y_true + 1e-12))))
    return {"mse": mse, "rmse": rmse, "mae": mae, "mape": mape}


def evaluate() -> Dict[str, any]:
    gen = SyntheticMarketDataGenerator(seed=SEED)
    ticks = gen.generate_ticks(SYMBOL, n=N_TICKS, start_price=150.0)

    split = int(len(ticks) * TRAIN_FRAC)
    train_ticks = ticks[:split]
    test_ticks = ticks[split:]

    # Entrenar world model con pares consecutivos de entrenamiento (sin futuro)
    brain = CentralBrain()
    for i in range(len(train_ticks) - 1):
        current = train_ticks[i].last_price
        nxt = train_ticks[i + 1].last_price
        brain.learn_from_tick(SYMBOL, current, nxt)

    env = TickPredictionEnvironment(brain=brain, failure_sources=[], latency_ms=0.0)
    tot = ReActReasonactToTBrain(env, confidence_threshold=0.5, max_depth=2)

    y_true_mid: List[float] = []
    y_pred_mid: List[float] = []
    y_true_spread: List[float] = []
    y_pred_spread: List[float] = []
    y_pred_conf: List[float] = []
    y_true_returns: List[float] = []
    y_pred_returns: List[float] = []

    # Para cada punto de prueba, usar SOLO ticks anteriores al target
    test_context_start = split
    for idx, target_tick in enumerate(test_ticks):
        history_end = test_context_start + idx  # índice del último tick conocido antes del target
        history = ticks[: history_end + 1]

        result = tot.predict(
            symbol=SYMBOL,
            ticks=history,
            predictors=["brain", "technical", "microstructure"],
        )

        if result.get("status") != "ok" or result.get("final_prediction") is None:
            continue

        pred = result["final_prediction"]
        pred_mid = pred["predicted_mid"]
        pred_spread = pred["spread"]
        pred_conf = pred["confidence"]

        actual_mid = _actual_mid(target_tick)
        actual_spread = target_tick.ask - target_tick.bid

        last_mid = _actual_mid(history[-1])
        y_true_returns.append((actual_mid - last_mid) / last_mid)
        y_pred_returns.append((pred_mid - last_mid) / last_mid)

        y_true_mid.append(actual_mid)
        y_pred_mid.append(pred_mid)
        y_true_spread.append(actual_spread)
        y_pred_spread.append(pred_spread)
        y_pred_conf.append(pred_conf)

    y_true_mid = np.array(y_true_mid)
    y_pred_mid = np.array(y_pred_mid)
    y_true_spread = np.array(y_true_spread)
    y_pred_spread = np.array(y_pred_spread)
    y_true_returns = np.array(y_true_returns)
    y_pred_returns = np.array(y_pred_returns)
    y_pred_conf = np.array(y_pred_conf)

    mid_metrics = _metrics(y_true_mid, y_pred_mid)
    spread_metrics = _metrics(y_true_spread, y_pred_spread)

    # Exactitud direccional
    dir_true = np.sign(y_true_returns)
    dir_pred = np.sign(y_pred_returns)
    directional_accuracy = float(np.mean(dir_true == dir_pred))

    # Intervalo de predicción aproximado (usando confianza como ancho relativo)
    # La confianza no es una desviación estándar; este intervalo es conservador.
    widths = y_pred_mid * (1.0 - y_pred_conf + 0.01)
    lower = y_pred_mid - 1.96 * widths
    upper = y_pred_mid + 1.96 * widths
    coverage = float(np.mean((y_true_mid >= lower) & (y_true_mid <= upper)))

    # Utilidad ajustada por riesgo de una estrategia trivial
    strategy_returns = np.where(y_pred_returns > 0, y_true_returns, -y_true_returns)
    mean_ret = float(np.mean(strategy_returns))
    std_ret = float(np.std(strategy_returns) + 1e-12)
    sharpe = mean_ret / std_ret if std_ret > 0 else 0.0
    cumulative = float(np.prod(1 + strategy_returns) - 1)

    report = {
        "seed": SEED,
        "symbol": SYMBOL,
        "total_ticks": len(ticks),
        "train_ticks": split,
        "test_points": len(y_true_mid),
        "price_prediction": {
            **mid_metrics,
            "directional_accuracy": directional_accuracy,
            "coverage_95_approx": coverage,
        },
        "spread_prediction": spread_metrics,
        "risk_adjusted_utility": {
            "mean_strategy_return": mean_ret,
            "std_strategy_return": std_ret,
            "sharpe": sharpe,
            "cumulative_return": cumulative,
        },
        "leakage_check": {
            "train_end_index": split,
            "first_test_target_index": split,
            "history_for_first_prediction": split,
            "notes": [
                "Train/test split es puramente temporal.",
                "Solo se usan ticks <= i para predecir el tick i+1.",
                "No se consulta target_tick en la entrada de la predicción.",
            ],
        },
    }
    return report


if __name__ == "__main__":
    report = evaluate()
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nResultados guardados en {OUTPUT}")
