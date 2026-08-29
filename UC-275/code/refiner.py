"""SelfRefiner — Generación de propuestas de refinamiento para UC-275.

Genera refinamientos específicos según la causa raíz detectada:
- model_error → ajuste de pesos, regularización.
- data_stale → reducir refresh interval, feeds en tiempo real.
- strategy_flaw → cambio de variante, reducción de riesgo.
- execution_error → órdenes límite, fragmentación.
- parameter_miscalibration → recalibración con ventana reciente.

Las propuestas se ordenan por beneficio neto (expected_improvement - risk_of_change).
"""
from __future__ import annotations

from typing import Any, Dict, List

from memory import ReflectionMemory
from models import (
    RefinementProposal,
    RootCauseAnalysis,
    SelfEvaluation,
)


class SelfRefiner:
    """Genera propuestas de refinamiento basadas en análisis de causa raíz."""

    def __init__(self, max_refinement_steps: int = 3,
                 min_improvement_threshold: float = 0.1) -> None:
        self.max_steps = max_refinement_steps
        self.min_improvement = min_improvement_threshold

    def propose_refinements(self, evaluation: SelfEvaluation,
                            root_cause: RootCauseAnalysis,
                            current_params: Dict[str, Any],
                            memory: ReflectionMemory) -> List[RefinementProposal]:
        """Genera propuestas de refinamiento según causa raíz."""
        proposals: List[RefinementProposal] = []

        handlers = {
            "model_error": self._refine_model,
            "data_stale": self._refine_data_freshness,
            "strategy_flaw": self._refine_strategy,
            "execution_error": self._refine_execution,
            "external_shock": self._refine_external,
            "parameter_miscalibration": self._refine_parameters,
        }

        handler = handlers.get(root_cause.category.value)
        if handler:
            if handler == self._refine_strategy:
                proposals.extend(handler(current_params, evaluation, memory))
            elif handler in (self._refine_model, self._refine_parameters):
                proposals.extend(handler(current_params, evaluation))
            else:
                proposals.extend(handler(current_params))

        # Lecciones aprendidas de la memoria
        action_type = current_params.get("_action_type", "unknown")
        lessons = memory.get_lessons_learned(action_type)
        if lessons["advice"]:
            proposals.append(RefinementProposal(
                trace_id=evaluation.trace_id,
                iteration=0,
                proposed_changes={"apply_lessons": lessons["advice"]},
                rationale=f"Aplicar lecciones de {lessons['total_episodes']} episodios previos",
                expected_improvement=lessons["success_rate"] * 0.2,
                risk_of_change=0.1,
            ))

        proposals.sort(key=lambda p: p.net_benefit, reverse=True)
        return proposals[:self.max_steps]

    def _refine_model(self, params: Dict, evaluation: SelfEvaluation) -> List[RefinementProposal]:
        proposals = []
        if "model_weights" in params:
            new_weights = {k: v * 0.9 for k, v in params["model_weights"].items()}
            proposals.append(RefinementProposal(
                trace_id=evaluation.trace_id,
                iteration=1,
                proposed_changes={"model_weights": new_weights},
                rationale="Reducir peso de features con alta varianza",
                expected_improvement=0.15,
                risk_of_change=0.2,
            ))

        proposals.append(RefinementProposal(
            trace_id=evaluation.trace_id,
            iteration=1,
            proposed_changes={"regularization": params.get("regularization", 0.01) * 2},
            rationale="Aumentar regularización para reducir overfitting",
            expected_improvement=0.1,
            risk_of_change=0.15,
        ))
        return proposals

    def _refine_data_freshness(self, params: Dict) -> List[RefinementProposal]:
        return [RefinementProposal(
            trace_id="",
            iteration=1,
            proposed_changes={
                "data_refresh_interval": max(10, params.get("data_refresh_interval", 60) // 2),
                "use_real_time_feeds": True,
            },
            rationale="Reducir intervalo de refresh de datos",
            expected_improvement=0.2,
            risk_of_change=0.1,
        )]

    def _refine_strategy(self, params: Dict, evaluation: SelfEvaluation,
                         memory: ReflectionMemory) -> List[RefinementProposal]:
        proposals = []
        lessons = memory.get_lessons_learned(params.get("_action_type", ""))
        if lessons["success_rate"] > 0.6:
            proposals.append(RefinementProposal(
                trace_id=evaluation.trace_id,
                iteration=1,
                proposed_changes={"strategy_variant": "alternative_A"},
                rationale="Cambiar a variante de estrategia con mejor historial",
                expected_improvement=0.25,
                risk_of_change=0.3,
            ))

        proposals.append(RefinementProposal(
            trace_id=evaluation.trace_id,
            iteration=1,
            proposed_changes={
                "risk_tolerance": params.get("risk_tolerance", 0.5) * 0.8,
                "position_size": params.get("position_size", 1.0) * 0.7,
            },
            rationale="Reducir exposición al riesgo tras desvío",
            expected_improvement=0.15,
            risk_of_change=0.2,
        ))
        return proposals

    def _refine_execution(self, params: Dict) -> List[RefinementProposal]:
        return [RefinementProposal(
            trace_id="",
            iteration=1,
            proposed_changes={
                "use_limit_orders": True,
                "slippage_tolerance": params.get("slippage_tolerance", 0.02) * 0.5,
                "split_large_orders": True,
            },
            rationale="Mejorar ejecución con órdenes límite y fragmentación",
            expected_improvement=0.2,
            risk_of_change=0.15,
        )]

    def _refine_external(self, params: Dict) -> List[RefinementProposal]:
        return [RefinementProposal(
            trace_id="",
            iteration=1,
            proposed_changes={
                "reduce_exposure": True,
                "position_size": params.get("position_size", 1.0) * 0.5,
                "hedge_ratio": params.get("hedge_ratio", 0.0) + 0.3,
            },
            rationale="Reducir exposición ante shock externo y aumentar cobertura",
            expected_improvement=0.15,
            risk_of_change=0.25,
        )]

    def _refine_parameters(self, params: Dict,
                           evaluation: SelfEvaluation) -> List[RefinementProposal]:
        return [RefinementProposal(
            trace_id=evaluation.trace_id,
            iteration=1,
            proposed_changes={
                "recalibrate": True,
                "calibration_window": 100,
            },
            rationale="Recalibrar parámetros con ventana reciente",
            expected_improvement=0.18,
            risk_of_change=0.1,
        )]
