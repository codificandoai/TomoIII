"""Motor Monte Carlo de simulación multi-plan para UC-264."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from config import ModelConfig
from models import CandidatePlan, PlanAction, SimulationResult, TravelPlanRequest, WorldModelState
from world_model import TravelWorldModel


class MonteCarloSimulator:
    """Simula planes candidatos mediante rollouts Monte Carlo."""

    def __init__(
        self,
        world_model: TravelWorldModel,
        config: ModelConfig,
    ) -> None:
        self.world_model = world_model
        self.config = config

    def simulate_plan(
        self,
        plan_id: str,
        actions: List[PlanAction],
        initial_state: WorldModelState,
        request: TravelPlanRequest,
        rng: Optional[np.random.Generator] = None,
    ) -> CandidatePlan:
        """Ejecuta N rollouts y devuelve el plan evaluado."""
        rng = rng or np.random.default_rng()
        simulations: List[SimulationResult] = []

        for _ in range(self.config.mc_simulations_per_plan):
            final_state, total_reward, success, violations = self.world_model.rollout(
                initial_state, actions, rng=rng
            )
            sim = SimulationResult(
                plan_id=plan_id,
                outcome=final_state.to_dict(),
                total_cost=final_state.total_cost,
                utility=total_reward,
                success=success,
                violated_constraints=violations,
            )
            simulations.append(sim)

        costs = [s.total_cost for s in simulations]
        utilities = [s.utility for s in simulations]
        successes = [s.success for s in simulations]

        expected_cost = float(np.mean(costs))
        expected_utility = float(np.mean(utilities))
        success_prob = float(np.mean(successes))
        cost_std = float(np.std(costs))

        # Penalizar riesgo (variabilidad de coste y probabilidad de fallo)
        risk_score = (
            (1 - success_prob) * 10.0 + cost_std / max(expected_cost, 1.0)
        )

        candidate = CandidatePlan(
            plan_id=plan_id,
            actions=[a.to_dict() for a in actions],
            estimated_total_cost=round(expected_cost, 2),
            estimated_success_prob=round(success_prob, 4),
            simulations=[s.to_dict() for s in simulations[:10]],  # guardar muestra
            expected_utility=round(expected_utility, 4),
            risk_score=round(risk_score, 4),
        )
        return candidate

    def simulate_candidates(
        self,
        candidate_actions: List[List[PlanAction]],
        initial_state: WorldModelState,
        request: TravelPlanRequest,
        rng: Optional[np.random.Generator] = None,
    ) -> List[CandidatePlan]:
        """Simula todos los planes candidatos."""
        rng = rng or np.random.default_rng()
        evaluated: List[CandidatePlan] = []
        for i, actions in enumerate(candidate_actions):
            plan_id = f"plan-{i+1:03d}"
            candidate = self.simulate_plan(
                plan_id, actions, initial_state, request, rng=rng
            )
            evaluated.append(candidate)
        return evaluated
