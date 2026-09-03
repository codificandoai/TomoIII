"""Motor Monte Carlo de simulación de estrategias de trading para UC-292."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from config import ModelConfig
from models import CandidateStrategy, SimulationResult, TradingRequest, WorldModelState
from world_model import TradingWorldModel


class MonteCarloSimulator:
    """Simula estrategias candidatas mediante rollouts Monte Carlo."""

    def __init__(
        self,
        world_model: TradingWorldModel,
        config: ModelConfig,
    ) -> None:
        self.world_model = world_model
        self.config = config

    def simulate_strategy(
        self,
        strategy_id: str,
        actions: List[Any],
        initial_state: WorldModelState,
        request: TradingRequest,
        rng: Optional[np.random.Generator] = None,
    ) -> CandidateStrategy:
        rng = rng or np.random.default_rng()
        from models import AgentAction

        agent_actions = [AgentAction(**a) if isinstance(a, dict) else a for a in actions]
        simulations: List[SimulationResult] = []

        for _ in range(self.config.mc_simulations_per_strategy):
            final_state, total_reward, success, violations = self.world_model.rollout(
                initial_state, agent_actions, rng=rng
            )
            sim = SimulationResult(
                strategy_id=strategy_id,
                outcome=final_state.to_dict(),
                total_return=final_state.portfolio_value - initial_state.portfolio_value,
                utility=total_reward,
                success=success,
                violated_constraints=violations,
            )
            simulations.append(sim)

        returns = [s.total_return for s in simulations]
        utilities = [s.utility for s in simulations]
        successes = [s.success for s in simulations]

        expected_return = float(np.mean(returns))
        expected_risk = float(np.std(returns))
        expected_utility = float(np.mean(utilities))
        success_prob = float(np.mean(successes))

        # Sharpe simplificado (sin tasa libre de riesgo)
        sharpe = expected_return / expected_risk if expected_risk > 1e-9 else 0.0

        # Penalizar riesgo y fallos
        risk_score = (
            (1 - success_prob) * 10.0
            + expected_risk / max(abs(expected_return), 1.0)
        )

        candidate = CandidateStrategy(
            strategy_id=strategy_id,
            name=strategy_id,
            actions=[a.to_dict() for a in agent_actions],
            expected_return=round(expected_return, 6),
            expected_risk=round(expected_risk, 6),
            sharpe=round(sharpe, 4),
            success_prob=round(success_prob, 4),
            risk_score=round(risk_score, 6),
            simulations=[s.to_dict() for s in simulations[:10]],
        )
        return candidate

    def simulate_candidates(
        self,
        candidate_actions: List[List[Any]],
        initial_state: WorldModelState,
        request: TradingRequest,
        rng: Optional[np.random.Generator] = None,
    ) -> List[CandidateStrategy]:
        """Simula todas las estrategias candidatas."""
        rng = rng or np.random.default_rng()
        evaluated: List[CandidateStrategy] = []
        for i, actions in enumerate(candidate_actions):
            strategy_id = f"strategy-{i+1:03d}"
            candidate = self.simulate_strategy(
                strategy_id, actions, initial_state, request, rng=rng
            )
            evaluated.append(candidate)
        return evaluated
