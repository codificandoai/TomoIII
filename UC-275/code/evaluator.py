"""MetricEvaluator — Autoevaluación multi-criterio ponderada para UC-275.

Implementa el patrón Self-Refine (Madaan et al., 2023):
- El agente genera una salida.
- Se evalúa contra criterios ponderados (correctness, completeness, clarity, efficiency).
- Score ponderado total determina el ReflectionOutcome.
- Los desvíos se cuantifican con severidad para decidir si se necesita refinamiento.

Soporta criterios personalizados y umbrales configurables.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from models import ReflectionOutcome, SelfEvaluation


class MetricEvaluator:
    """
    Evalúa métricas de rendimiento contra expectativas.
    Scoring multi-criterio ponderado estilo Self-Refine.
    """

    def __init__(self, metric_weights: Dict[str, float],
                 thresholds: Optional[Dict[str, Tuple[float, float]]] = None) -> None:
        """
        Args:
            metric_weights: {metric_name: weight} (se normaliza internamente).
            thresholds: {metric_name: (min_acceptable, target)}.
        """
        total = sum(metric_weights.values())
        self.weights = {k: v / total for k, v in metric_weights.items()}
        self.thresholds = thresholds or {}

    def evaluate(self, actual: Dict[str, float],
                 expected: Dict[str, float]) -> SelfEvaluation:
        """Evalúa resultado contra expectativas, devuelve SelfEvaluation."""
        metric_scores: Dict[str, float] = {}
        deviations = []
        severity_sum = 0.0

        for metric, weight in self.weights.items():
            actual_val = actual.get(metric, 0.0)
            expected_val = expected.get(metric, actual_val)

            score = self._score_metric(metric, actual_val, expected_val)
            metric_scores[metric] = round(score, 4)

            min_acc, target = self.thresholds.get(metric, (0.0, expected_val))
            if actual_val < min_acc:
                deviations.append(f"{metric}: {actual_val:.3f} < {min_acc:.3f} (min)")
                severity_sum += (min_acc - actual_val) / max(min_acc, 1e-9)
            elif expected_val != 0 and abs(actual_val - expected_val) / max(abs(expected_val), 1e-9) > 0.2:
                deviations.append(f"{metric}: {actual_val:.3f} vs expected {expected_val:.3f}")
                severity_sum += 0.3

        total_score = sum(
            metric_scores.get(m, 0.5) * w for m, w in self.weights.items()
        )
        total_score = round(min(1.0, max(0.0, total_score)), 4)

        outcome = self._classify_outcome(total_score)
        expectations_met = len(deviations) == 0
        severity = min(1.0, severity_sum / max(len(self.weights), 1))

        return SelfEvaluation(
            trace_id="",
            outcome=outcome,
            score=total_score,
            metric_breakdown=metric_scores,
            expectations_met=expectations_met,
            deviations=deviations,
            severity=round(severity, 4),
        )

    def evaluate_text_output(self, criteria_scores: Dict[str, float]) -> SelfEvaluation:
        """Evalúa output de texto con scores por criterio (estilo Self-Refine).

        Args:
            criteria_scores: {criterion: score_0_to_1} — ej. {"correctness": 0.9, ...}
        """
        metric_scores: Dict[str, float] = {}
        deviations = []
        severity_sum = 0.0

        for criterion, weight in self.weights.items():
            score = criteria_scores.get(criterion, 0.5)
            score = min(1.0, max(0.0, score))
            metric_scores[criterion] = round(score, 4)

            if score < 0.5:
                deviations.append(f"{criterion}: {score:.3f} < 0.500 (threshold)")
                severity_sum += (0.5 - score)

        total_score = sum(
            metric_scores.get(m, 0.5) * w for m, w in self.weights.items()
        )
        total_score = round(min(1.0, max(0.0, total_score)), 4)

        outcome = self._classify_outcome(total_score)
        severity = min(1.0, severity_sum / max(len(self.weights), 1))

        return SelfEvaluation(
            trace_id="",
            outcome=outcome,
            score=total_score,
            metric_breakdown=metric_scores,
            expectations_met=len(deviations) == 0,
            deviations=deviations,
            severity=round(severity, 4),
        )

    def _score_metric(self, metric: str, actual: float, expected: float) -> float:
        """Score individual [0, 1] para una métrica."""
        if expected == 0:
            return 1.0 if actual == 0 else 0.0
        ratio = actual / expected
        if ratio >= 1.0:
            return min(1.0, 0.8 + 0.2 * min(ratio - 1.0, 1.0))
        return max(0.0, ratio)

    @staticmethod
    def _classify_outcome(score: float) -> ReflectionOutcome:
        if score >= 0.9:
            return ReflectionOutcome.EXCELLENT
        if score >= 0.7:
            return ReflectionOutcome.GOOD
        if score >= 0.5:
            return ReflectionOutcome.ACCEPTABLE
        if score >= 0.3:
            return ReflectionOutcome.POOR
        return ReflectionOutcome.FAILURE
