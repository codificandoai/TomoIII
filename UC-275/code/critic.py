"""SelfCritic — Análisis de causa raíz para UC-275.

Combina heurísticas de dominio con razonamiento estructurado:
- Heurísticas por categoría (model_error, data_stale, strategy_flaw, etc.).
- Fallback analysis cuando las heurísticas no son concluyentes.
- Descripciones legibles para auditoría.

Inspirado en Reflexion (Shinn et al., NeurIPS 2023):
el agente reflexiona sobre las causas de sus errores.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from models import (
    CauseCategory,
    OutcomeObservation,
    RootCauseAnalysis,
    SelfEvaluation,
)


class SelfCritic:
    """
    Analiza causas raíz de desviaciones.
    Combina heurísticas con razonamiento estructurado.
    """

    CAUSE_HEURISTICS: Dict[str, List[Callable[[OutcomeObservation], bool]]] = {
        "model_error": [
            lambda obs: abs(obs.metrics.get("prediction_error", 0)) > 0.3,
            lambda obs: obs.metrics.get("model_confidence", 1.0) < 0.5,
        ],
        "data_stale": [
            lambda obs: obs.metrics.get("data_age_seconds", 0) > 300,
            lambda obs: obs.metrics.get("market_volatility", 0) > 0.5,
        ],
        "strategy_flaw": [
            lambda obs: obs.metrics.get("opportunity_cost", 0) > 0.2,
            lambda obs: obs.metrics.get("relative_performance", 1.0) < 0.7,
        ],
        "execution_error": [
            lambda obs: obs.metrics.get("slippage", 0) > 0.05,
            lambda obs: obs.metrics.get("latency_ms", 0) > 1000,
        ],
        "external_shock": [
            lambda obs: obs.metrics.get("market_regime_change", 0) > 0.7,
            lambda obs: obs.metrics.get("black_swan_indicator", 0) > 0.5,
        ],
        "parameter_miscalibration": [
            lambda obs: abs(
                obs.metrics.get("risk_realized", 0) - obs.metrics.get("risk_expected", 0)
            ) > 0.2,
        ],
    }

    CAUSE_DESCRIPTIONS = {
        "model_error": "Modelo interno impreciso",
        "data_stale": "Datos de entrada obsoletos o mercado muy volátil",
        "strategy_flaw": "Estrategia subóptima vs alternativas disponibles",
        "execution_error": "Errores en ejecución (slippage, latencia)",
        "external_shock": "Evento externo no anticipado",
        "parameter_miscalibration": "Parámetros mal calibrados (riesgo vs realizado)",
    }

    def analyze(self, evaluation: SelfEvaluation,
                observation: OutcomeObservation,
                context: Dict[str, Any] | None = None) -> RootCauseAnalysis:
        """Analiza causa raíz de los desvíos detectados."""
        cause_scores: Dict[str, float] = {}
        for cause, heuristics in self.CAUSE_HEURISTICS.items():
            score = sum(1 for h in heuristics if h(observation)) / len(heuristics)
            cause_scores[cause] = score

        primary = max(cause_scores, key=cause_scores.get)
        confidence = cause_scores[primary]

        contributing = [
            c for c, s in cause_scores.items()
            if s > 0.3 and c != primary
        ]

        if confidence < 0.3:
            primary, contributing = self._fallback_analysis(evaluation, observation)
            confidence = 0.5

        return RootCauseAnalysis(
            trace_id=evaluation.trace_id,
            primary_cause=self._describe_cause(primary, evaluation),
            contributing_factors=[self._describe_cause(c, evaluation) for c in contributing],
            category=CauseCategory(primary),
            confidence=round(confidence, 4),
        )

    def _describe_cause(self, cause: str, evaluation: SelfEvaluation) -> str:
        base = self.CAUSE_DESCRIPTIONS.get(cause, f"Causa no clasificada: {cause}")
        if cause == "model_error" and evaluation.deviations:
            base += f". Desvíos: {evaluation.deviations[:2]}"
        return base

    def _fallback_analysis(self, evaluation: SelfEvaluation,
                           observation: OutcomeObservation) -> Tuple[str, List[str]]:
        """Análisis fallback basado en severidad y desvíos."""
        if evaluation.severity > 0.7:
            return "execution_error", ["strategy_flaw"]
        if len(evaluation.deviations) > 2:
            return "parameter_miscalibration", ["model_error"]
        return "strategy_flaw", []
