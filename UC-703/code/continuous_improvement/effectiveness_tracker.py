"""Seguimiento de efectividad de las mejoras implementadas."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from continuous_improvement.models_ci import EffectivenessMeasurement


class EffectivenessTracker:
    """
    Mide si una recomendación aprobada realmente reduce recurrencia o
    mejora la métrica objetivo.
    """

    def __init__(self) -> None:
        self._measurements: List[EffectivenessMeasurement] = []
        self._baselines: Dict[str, float] = {}

    def register_baseline(self, metric_name: str, value: float) -> None:
        self._baselines[metric_name] = value

    def measure(
        self,
        recommendation_id: str,
        metric_name: str,
        after_value: float,
    ) -> EffectivenessMeasurement:
        before = self._baselines.get(metric_name, after_value)
        delta = before - after_value
        improvement_pct = round((delta / before) * 100, 2) if before else 0.0
        m = EffectivenessMeasurement(
            recommendation_id=recommendation_id,
            metric_name=metric_name,
            before_value=before,
            after_value=after_value,
            improvement_pct=improvement_pct,
        )
        self._measurements.append(m)
        return m

    def summary(self) -> Dict[str, Any]:
        if not self._measurements:
            return {"measurements": 0, "avg_improvement_pct": 0.0}
        avg = sum(m.improvement_pct for m in self._measurements) / len(self._measurements)
        return {
            "measurements": len(self._measurements),
            "avg_improvement_pct": round(avg, 2),
        }
