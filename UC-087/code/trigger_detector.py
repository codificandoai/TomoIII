"""
UC-087 — Detección de triggers, backdoors y caídas repentinas de performance.

Monitorea slices de datos, entropía de predicciones y activación de
triggers para detectar backdoors o envenenamiento.
"""

import math
import statistics
from typing import List, Dict, Any, Callable, Tuple

from models_087 import DataPoint, SliceAlert, TriggerReport


class TriggerDetector:
    """
    Detección de backdoors mediante monitoreo por segmentos y análisis de
entropía/confianza de predicciones.
    """

    def __init__(self, slice_drop_threshold: float = 0.30, entropy_zscore: float = 2.0):
        self.slice_drop_threshold = slice_drop_threshold
        self.entropy_zscore = entropy_zscore

    def _predict_fn(self, model: Any, features: List[float]) -> float:
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(features)
            if isinstance(proba, (list, tuple)):
                return float(proba[1]) if len(proba) > 1 else float(proba[0])
            return float(proba)
        if hasattr(model, "predict"):
            pred = model.predict(features)
            if isinstance(pred, (list, tuple)):
                return float(pred[0])
            return float(pred)
        return float(model(features))

    def _predict_label(self, model: Any, features: List[float]) -> int:
        proba = self._predict_fn(model, features)
        return 1 if proba >= 0.5 else 0

    def _accuracy(self, model: Any, data: List[DataPoint]) -> float:
        if not data:
            return 0.0
        correct = 0
        total = 0
        for dp in data:
            if dp.label is None:
                continue
            pred = self._predict_label(model, dp.features)
            if pred == dp.label:
                correct += 1
            total += 1
        return correct / total if total > 0 else 0.0

    def _entropy(self, probabilities: List[float]) -> float:
        total = 0.0
        for p in probabilities:
            p = max(1e-9, min(1.0 - 1e-9, p))
            total += -(p * math.log(p) + (1 - p) * math.log(1 - p))
        return total / len(probabilities) if probabilities else 0.0

    def detect_slice_drops(
        self,
        model: Any,
        data: List[DataPoint],
        baseline_metrics: Dict[str, float],
        feature_slicing: bool = True,
    ) -> List[SliceAlert]:
        """
        Revisa accuracy en slices definidos por feature_index > threshold.
        Si la caída supera slice_drop_threshold, emite alerta.
        """
        alerts = []
        if not data:
            return alerts
        dim = len(data[0].features)

        # Slices por cada feature por encima del percentil 90
        for j in range(dim):
            values = [dp.features[j] for dp in data]
            threshold = self._percentile(values, 90)
            slice_data = [dp for dp in data if dp.features[j] > threshold]
            if len(slice_data) < 5:
                continue
            current_acc = self._accuracy(model, slice_data)
            baseline_key = f"slice_feature_{j}_acc"
            baseline_acc = baseline_metrics.get(baseline_key, current_acc)
            drop = baseline_acc - current_acc
            if drop > self.slice_drop_threshold:
                alerts.append(SliceAlert(
                    slice_name=f"feature_{j}_top10",
                    baseline_accuracy=baseline_acc,
                    current_accuracy=current_acc,
                    drop=drop,
                    severity="P1",
                    description=f"Caída del {drop:.1%} en slice feature_{j} > {threshold:.2f}. Posible trigger/backdoor.",
                ))

        # Slice por metadata de trigger si existe
        triggered = [dp for dp in data if dp.metadata.get("trigger")]
        if len(triggered) >= 5:
            current_acc = self._accuracy(model, triggered)
            baseline_acc = baseline_metrics.get("trigger_slice_acc", current_acc)
            drop = baseline_acc - current_acc
            if drop > self.slice_drop_threshold:
                alerts.append(SliceAlert(
                    slice_name="trigger_injected",
                    baseline_accuracy=baseline_acc,
                    current_accuracy=current_acc,
                    drop=drop,
                    severity="P1",
                    description="Caída en muestras marcadas con trigger; posible backdoor activado.",
                ))

        return alerts

    def detect_entropy_anomaly(
        self,
        model: Any,
        data: List[DataPoint],
        baseline_entropy: float = 0.5,
    ) -> Tuple[bool, float]:
        """Detecta si la entropía media se desvía del baseline."""
        if not data:
            return False, 0.0
        probabilities = [self._predict_fn(model, dp.features) for dp in data]
        current_entropy = self._entropy(probabilities)
        std = max(0.05, baseline_entropy * 0.1)
        zscore = abs(current_entropy - baseline_entropy) / std
        alert = zscore > self.entropy_zscore
        return alert, zscore

    def detect_suspicious_features(self, data: List[DataPoint]) -> List[str]:
        """Identifica features con valores constantes o extremos (posibles triggers)."""
        if not data:
            return []
        dim = len(data[0].features)
        suspicious = []
        for j in range(dim):
            values = [dp.features[j] for dp in data]
            unique = len(set(values))
            if unique == 1:
                suspicious.append(f"feature_{j}_constant")
            elif self._percentile(values, 99) - self._percentile(values, 1) > 10 * (statistics.stdev(values) + 1e-6):
                suspicious.append(f"feature_{j}_extreme_spread")
        return suspicious

    def _percentile(self, values: List[float], p: float) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        k = (len(sorted_vals) - 1) * (p / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_vals[int(k)]
        return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)

    def evaluate(
        self,
        model: Any,
        data: List[DataPoint],
        baseline_metrics: Dict[str, float],
    ) -> TriggerReport:
        """Ejecuta todas las comprobaciones de backdoor/trigger."""
        entropy_alert, entropy_zscore = self.detect_entropy_anomaly(model, data, baseline_metrics.get("entropy", 0.5))
        slice_alerts = self.detect_slice_drops(model, data, baseline_metrics)
        suspicious_features = self.detect_suspicious_features(data)

        return TriggerReport(
            entropy_alert=entropy_alert,
            entropy_zscore=entropy_zscore,
            slice_alerts=slice_alerts,
            suspicious_features=suspicious_features,
        )


class AnyModel:
    pass
