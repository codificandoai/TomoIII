"""Agente Crítico para UC-264: selecciona el mejor plan basado en utilidad esperada, riesgo y alineación."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import ModelConfig
from models import CandidatePlan, PlanEvaluation


class PlanCritic:
    """Evalúa y ranquea planes candidatos simulados."""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    def evaluate(self, candidates: List[CandidatePlan]) -> List[PlanEvaluation]:
        evaluations = []
        for c in candidates:
            alignment = self._alignment_score(c)
            budget_penalty = 0.0
            # penalización leve por coste alto en relación a utilidad
            if c.estimated_total_cost > 0 and c.estimated_success_prob > 0:
                budget_penalty = max(
                    0.0,
                    c.estimated_total_cost / 1000.0 - c.expected_utility * 0.5
                )

            final_score = (
                c.expected_utility
                - self.config.risk_aversion * c.risk_score
                + 0.5 * alignment
                - budget_penalty
            )
            evaluations.append(
                PlanEvaluation(
                    plan_id=c.plan_id,
                    expected_utility=round(c.expected_utility, 4),
                    expected_cost=round(c.estimated_total_cost, 2),
                    success_probability=round(c.estimated_success_prob, 4),
                    risk_score=round(c.risk_score, 4),
                    alignment_score=round(alignment, 4),
                    final_score=round(final_score, 4),
                    explanation=(
                        f"Plan {c.plan_id} [{c.strategy}]: utility={c.expected_utility:.2f}, "
                        f"cost={c.estimated_total_cost:.2f}, success={c.estimated_success_prob:.2%}, "
                        f"risk={c.risk_score:.2f}, alignment={alignment:.2f}."
                    ),
                )
            )
        evaluations.sort(key=lambda e: e.final_score, reverse=True)
        return evaluations

    def select_best(
        self, candidates: List[CandidatePlan]
    ) -> Optional[CandidatePlan]:
        if not candidates:
            return None
        evaluations = self.evaluate(candidates)
        best_id = evaluations[0].plan_id
        for c in candidates:
            if c.plan_id == best_id:
                c.final_score = evaluations[0].final_score
                c.expected_utility = evaluations[0].expected_utility
                c.risk_score = evaluations[0].risk_score
                c.alignment_score = evaluations[0].alignment_score
                c.reasoning = evaluations[0].explanation
                return c
        return None

    def _alignment_score(self, candidate: CandidatePlan) -> float:
        """Score heurístico de alineación con preferencias implícitas del plan."""
        score = 0.0
        for action in candidate.actions:
            details = action.get("details", {})
            if action.get("action_type") == "flight" and details.get("direct"):
                score += 0.2
            if action.get("action_type") == "hotel" and details.get("rating", 0) >= 4.0:
                score += 0.2
        return min(1.0, score)
