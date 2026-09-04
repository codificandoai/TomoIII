"""Agente Crítico para UC-292: selecciona la mejor estrategia de trading."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import ModelConfig
from models import CandidateStrategy, StrategyEvaluation


class StrategyCritic:
    """Evalúa y ranquea estrategias candidatas simuladas."""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    def evaluate(self, candidates: List[CandidateStrategy]) -> List[StrategyEvaluation]:
        evaluations = []
        for c in candidates:
            alignment = self._alignment_score(c)
            risk_penalty = c.expected_risk * self.config.risk_aversion
            return_bonus = c.expected_return * self.config.return_weight
            alignment_bonus = alignment * self.config.alignment_weight

            final_score = (
                return_bonus
                - risk_penalty
                + alignment_bonus
            )
            evaluations.append(
                StrategyEvaluation(
                    strategy_id=c.strategy_id,
                    expected_return=round(c.expected_return, 6),
                    expected_risk=round(c.expected_risk, 6),
                    success_probability=round(c.success_prob, 4),
                    risk_score=round(c.risk_score, 4),
                    alignment_score=round(alignment, 4),
                    final_score=round(final_score, 6),
                    explanation=(
                        f"Strategy {c.name}: expected_return={c.expected_return:.4f}, "
                        f"risk={c.expected_risk:.4f}, success={c.success_prob:.2%}, "
                        f"sharpe={c.sharpe:.4f}, alignment={alignment:.2f}."
                    ),
                )
            )
        evaluations.sort(key=lambda e: e.final_score, reverse=True)
        return evaluations

    def select_best(
        self, candidates: List[CandidateStrategy]
    ) -> Optional[CandidateStrategy]:
        if not candidates:
            return None
        evaluations = self.evaluate(candidates)
        eval_by_id = {e.strategy_id: e for e in evaluations}
        for c in candidates:
            e = eval_by_id.get(c.strategy_id)
            if e is not None:
                c.final_score = e.final_score
                c.expected_return = e.expected_return
                c.risk_score = e.risk_score
                c.alignment_score = e.alignment_score
                if not c.reasoning:
                    c.reasoning = e.explanation
        best_id = evaluations[0].strategy_id
        for c in candidates:
            if c.strategy_id == best_id:
                return c
        return None

    def _alignment_score(self, candidate: CandidateStrategy) -> float:
        """Score heurístico de alineación con el régimen implícito de la estrategia."""
        score = 0.0
        for action in candidate.actions:
            metadata = action.metadata or {}
            strategy = metadata.get("strategy", "")
            if strategy in ("momentum_buy", "mean_reversion_buy") and action.side == "BUY":
                score += 0.2
            if strategy in ("momentum_sell", "mean_reversion_sell") and action.side == "SELL":
                score += 0.2
            if strategy == "hold" and action.side == "HOLD":
                score += 0.05
        return min(1.0, score)
