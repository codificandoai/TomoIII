"""Validación exhaustiva del cerebro central (CentralBrain) de UC-292.

Genera un reporte con métricas porcentuales de predicción de ticks,
retroalimentación y consistencia del estado del cerebro.
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Tuple

import numpy as np

from central_brain import CentralBrain
from config import get_config
from market_data import SyntheticMarketDataGenerator
from models import TradingRequest


def mean_absolute_percentage_error(y_true: List[float], y_pred: List[float]) -> float:
    errors = [abs((t - p) / t) * 100 for t, p in zip(y_true, y_pred) if t != 0]
    return float(np.mean(errors)) if errors else 0.0


def directional_accuracy(y_true: List[float], y_pred: List[float]) -> float:
    if len(y_true) < 2 or len(y_pred) < 2:
        return 0.0
    correct = 0
    total = 0
    for i in range(1, len(y_true)):
        actual_dir = np.sign(y_true[i] - y_true[i - 1])
        pred_dir = np.sign(y_pred[i] - y_pred[i - 1])
        if actual_dir == pred_dir:
            correct += 1
        total += 1
    return (correct / total) * 100 if total else 0.0


def within_threshold_pct(y_true: List[float], y_pred: List[float], threshold: float) -> float:
    within = sum(1 for t, p in zip(y_true, y_pred) if t != 0 and abs((t - p) / t) <= threshold)
    return (within / len(y_true)) * 100 if y_true else 0.0


def evaluate_brain(symbol: str = "AAPL", n_train: int = 600, n_test: int = 100, seed: int = 42) -> Dict[str, Any]:
    cfg = get_config()
    gen = SyntheticMarketDataGenerator(cfg.market, seed=seed)
    train_ticks = gen.generate_ticks(symbol, n=n_train)
    test_ticks = gen.generate_ticks(symbol, n=n_test, start_price=train_ticks[-1].last_price)

    brain = CentralBrain(cfg)

    # Fase 1: entrenar con pares consecutivos
    for i in range(len(train_ticks) - 1):
        brain.learn_from_tick(
            symbol,
            train_ticks[i].last_price,
            train_ticks[i + 1].last_price,
        )

    trained = brain.world_model._has_trained_return_model()

    # Fase 2: predecir paso a paso en test (observar tick i, predecir i+1)
    predictions: List[float] = []
    baseline_preds: List[float] = []
    actuals: List[float] = []
    uncertainties: List[float] = []

    for i in range(len(test_ticks) - 1):
        brain.observe(TradingRequest(symbols=[symbol], ticks=[test_ticks[i]]))
        pred = brain.predict_next_price(symbol)
        predictions.append(pred["predicted_next_price"])
        baseline_preds.append(test_ticks[i].last_price)
        actuals.append(test_ticks[i + 1].last_price)
        uncertainties.append(pred["uncertainty"])

    mape = mean_absolute_percentage_error(actuals, predictions)
    baseline_mape = mean_absolute_percentage_error(actuals, baseline_preds)
    rmse = float(np.sqrt(np.mean([(a - p) ** 2 for a, p in zip(actuals, predictions)])))
    baseline_rmse = float(np.sqrt(np.mean([(a - p) ** 2 for a, p in zip(actuals, baseline_preds)])))
    dir_acc = directional_accuracy(actuals, predictions)
    baseline_dir_acc = directional_accuracy(actuals, baseline_preds)
    within_1 = within_threshold_pct(actuals, predictions, 0.01)
    within_5 = within_threshold_pct(actuals, predictions, 0.05)
    within_10 = within_threshold_pct(actuals, predictions, 0.10)
    mean_uncertainty = float(np.mean(uncertainties))
    mape_improvement = ((baseline_mape - mape) / baseline_mape * 100) if baseline_mape else 0.0
    rmse_improvement = ((baseline_rmse - rmse) / baseline_rmse * 100) if baseline_rmse else 0.0

    # Fase 3: verificar consistencia del estado del cerebro
    context = brain.get_context(symbol)
    state = brain.to_dict()

    consistency = {
        "has_snapshot": context["snapshot"] is not None,
        "has_belief": context["belief"] is not None,
        "has_price_prediction": "predicted_next_price" in context.get("price_prediction", {}),
        "has_risk_context": "volatility" in context.get("risk_context", {}),
        "state_serializable": isinstance(state, dict) and "snapshots" in state,
    }

    return {
        "symbol": symbol,
        "trained_model": trained,
        "training_samples": n_train,
        "test_samples": n_test,
        "mape_percent": round(mape, 4),
        "baseline_mape_percent": round(baseline_mape, 4),
        "mape_improvement_over_baseline_percent": round(mape_improvement, 2),
        "rmse": round(rmse, 4),
        "baseline_rmse": round(baseline_rmse, 4),
        "rmse_improvement_over_baseline_percent": round(rmse_improvement, 2),
        "directional_accuracy_percent": round(dir_acc, 2),
        "baseline_directional_accuracy_percent": round(baseline_dir_acc, 2),
        "within_1_percent": round(within_1, 2),
        "within_5_percent": round(within_5, 2),
        "within_10_percent": round(within_10, 2),
        "mean_uncertainty": round(mean_uncertainty, 4),
        "consistency_checks": consistency,
        "consistency_percent": round(sum(consistency.values()) / len(consistency) * 100, 2),
        "sample_predictions": [
            {
                "actual": round(a, 4),
                "predicted": round(p, 4),
                "error_pct": round(abs((a - p) / a) * 100, 4) if a else None,
            }
            for a, p in zip(actuals[:10], predictions[:10])
        ],
    }


def main() -> None:
    report = evaluate_brain()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    with open("brain_validation_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
