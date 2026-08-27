"""Nodos LangGraph del sistema model-based probabilístico multi-agente para UC-265."""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

import numpy as np

from config import AppConfig
from critic import PlanCritic
from models import (
    BeliefState,
    ExecutionResult,
    HiddenState,
    Observation,
    PlanAction,
    PlanEvaluation,
    TravelPlanRequest,
    WorldModelObservation,
    WorldModelState,
    now_iso,
)
from planner import PlanGenerator
from simulator import MonteCarloSimulator
from travel_world import TravelWorldSimulator
from world_model import TravelWorldModel


class ModelBasedNodes:
    """Nodos del workflow de planificación basada en modelo probabilístico."""

    def __init__(
        self,
        config: AppConfig,
        world_model: TravelWorldModel,
        simulator: MonteCarloSimulator,
        critic: PlanCritic,
        planner: PlanGenerator,
        executor: TravelWorldSimulator,
    ) -> None:
        self.config = config
        self.world_model = world_model
        self.simulator = simulator
        self.critic = critic
        self.planner = planner
        self.executor = executor
        self.rng = np.random.default_rng(config.world.seed)

    def _log(self, node: str, message: str) -> Dict[str, Any]:
        return {"node": node, "message": message, "timestamp": now_iso()}

    def _reflection(self, stage: str, message: str) -> Dict[str, Any]:
        return {"stage": stage, "message": message, "timestamp": now_iso()}

    # ------------------------------------------------------------------
    # 1. Entrada, validación y construcción del world model + creencia
    # ------------------------------------------------------------------
    def parse_and_build_model_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        request = TravelPlanRequest.from_dict(state["request"])
        missing: List[str] = []
        for field in ("origin", "destination", "departure_date"):
            if not getattr(request, field):
                missing.append(f"{field} is required")
        if missing:
            return {
                "status": "awaiting_input",
                "missing_info": missing,
                "reflections": [self._reflection("input", f"Missing fields: {missing}")],
                "logs": [self._log("input", "Validation failed")],
            }

        initial_state = WorldModelState(
            request_id=request.request_id,
            step=0,
            remaining_budget=request.budget,
            currency=request.currency,
            preferences=request.preferences,
            constraints=request.constraints,
        )

        belief = self.world_model.initialize_belief(request)

        return {
            "status": "generating",
            "world_model": self.world_model.to_dict(),
            "belief_state": belief.to_dict(),
            "reflections": [
                self._reflection(
                    "world_model",
                    f"Built probabilistic world model for {request.origin}->{request.destination}. "
                    f"Loaded {len(self.world_model.estimates)} empirical estimates. "
                    f"Partial observability={self.config.world.partial_observability}.",
                )
            ],
            "logs": [self._log("world_model", f"Built model for request {request.request_id}")],
        }

    # ------------------------------------------------------------------
    # 2. Generar candidatos (incluyendo MCTS completo)
    # ------------------------------------------------------------------
    def generate_candidates_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        request = TravelPlanRequest.from_dict(state["request"])
        initial_state = WorldModelState(
            request_id=request.request_id,
            step=0,
            remaining_budget=request.budget,
            currency=request.currency,
            preferences=request.preferences,
            constraints=request.constraints,
        )

        action_sequences, meta = self.planner.generate(
            request,
            world_model=self.world_model,
            initial_state=initial_state,
        )
        candidates = [
            {
                "plan_id": f"plan-{i+1:03d}",
                "strategy": meta.get("strategies", ["unknown"])[-1] if i == 0 else "heuristic",
                "actions": [a.to_dict() for a in seq],
            }
            for i, seq in enumerate(action_sequences)
        ]
        if candidates:
            candidates[0]["strategy"] = "mcts" if len(candidates) > 0 else "heuristic"

        return {
            "status": "simulating",
            "candidates": candidates,
            "reflections": [
                self._reflection(
                    "planner",
                    f"Generated {len(candidates)} candidate plans using strategies: {meta.get('strategies')}. "
                    f"Includes MCTS tree search.",
                )
            ],
            "logs": [self._log("planner", f"Generated {len(candidates)} candidates")],
        }

    # ------------------------------------------------------------------
    # 3. Simular candidatos con Monte Carlo
    # ------------------------------------------------------------------
    def simulate_candidates_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        request = TravelPlanRequest.from_dict(state["request"])
        initial_state = WorldModelState(
            request_id=request.request_id,
            step=0,
            remaining_budget=request.budget,
            currency=request.currency,
            preferences=request.preferences,
            constraints=request.constraints,
        )
        candidate_actions: List[List[PlanAction]] = []
        for c in state.get("candidates", []):
            actions = [PlanAction(**a) for a in c.get("actions", [])]
            candidate_actions.append(actions)

        evaluated = self.simulator.simulate_candidates(
            candidate_actions,
            initial_state,
            request,
            rng=self.rng,
        )

        # Registrar transiciones simuladas para entrenamiento futuro
        for c in evaluated:
            for sim in c.simulations[:3]:
                self.world_model.record_transition(
                    TransitionAdapter(c.actions, sim).to_transition()
                )

        return {
            "status": "evaluating",
            "candidates": [c.to_dict() for c in evaluated],
            "world_model": self.world_model.to_dict(),
            "reflections": [
                self._reflection(
                    "simulator",
                    f"Simulated {len(evaluated)} candidate plans with {self.config.model.mc_simulations_per_plan} rollouts each. "
                    f"Recorded transitions for retraining.",
                )
            ],
            "logs": [self._log("simulator", f"Simulated {len(evaluated)} candidates")],
        }

    # ------------------------------------------------------------------
    # 4. Evaluar y seleccionar
    # ------------------------------------------------------------------
    def evaluate_and_select_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        candidates = [CandidatePlanAdapter(c).to_candidate() for c in state.get("candidates", [])]
        best = self.critic.select_best(candidates)
        evaluations = self.critic.evaluate(candidates)
        if best is None:
            return {
                "status": "awaiting_input",
                "reflections": [self._reflection("critic", "No candidate plans available.")],
                "logs": [self._log("critic", "No candidates")],
            }
        return {
            "status": "ready_to_execute",
            "selected_plan": best.to_dict(),
            "evaluations": [e.to_dict() for e in evaluations],
            "reflections": [
                self._reflection(
                    "critic",
                    f"Selected plan {best.plan_id} with score {best.final_score:.4f} after evaluating {len(evaluations)} plans.",
                )
            ],
            "logs": [self._log("critic", f"Selected plan {best.plan_id}")],
        }

    # ------------------------------------------------------------------
    # 5. Confirmación / Ejecución
    # ------------------------------------------------------------------
    def confirm_or_execute_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        request = TravelPlanRequest.from_dict(state["request"])
        selected = state.get("selected_plan")
        if not selected:
            return {"status": "failed", "reflections": [self._reflection("executor", "No plan selected")]}

        if self.config.agent.require_confirmation_irreversible and not request.confirm_irreversible:
            return {
                "status": "awaiting_confirmation",
                "requires_confirmation": True,
                "reflections": [
                    self._reflection("executor", "Plan ready but requires user confirmation before booking.")
                ],
                "logs": [self._log("executor", "Awaiting confirmation")],
            }
        return {"status": "executing", "requires_confirmation": False}

    def execute_plan_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        selected = state.get("selected_plan") or {}
        actions = [PlanAction(**a) for a in selected.get("actions", [])]
        results: List[Dict[str, Any]] = []
        total_cost = 0.0
        failed: List[str] = []
        successful = True

        # Generar observaciones ruidosas si el entorno es parcialmente observable
        observations: List[Dict[str, Any]] = []
        partial = self.config.world.partial_observability
        belief = BeliefState(**state.get("belief_state", {}))

        for action in actions:
            if action.action_type == "flight":
                outcome = self.executor.book_flight(action.item_id)
            elif action.action_type == "hotel":
                outcome = self.executor.book_hotel(action.item_id)
            else:
                outcome = {"status": "BOOKED", "confirmation": "AUTO-OK"}

            if outcome.get("status") == "BOOKED":
                total_cost += outcome.get("actual_cost", action.estimated_cost)
                action.details["confirmation"] = outcome.get("confirmation")
                results.append({
                    "action_id": action.action_id,
                    "item_id": action.item_id,
                    "status": "BOOKED",
                    "confirmation": outcome.get("confirmation"),
                    "cost": outcome.get("actual_cost", action.estimated_cost),
                })
            else:
                successful = False
                failed.append(action.item_id)
                results.append({
                    "action_id": action.action_id,
                    "item_id": action.item_id,
                    "status": "FAILED",
                    "error": outcome.get("error"),
                })

            # En entornos parcialmente observables se generan observaciones ruidosas
            if partial:
                obs = self.world_model.observe(action.details, rng=self.rng)
                observations.append(obs.to_dict())
                belief = self.world_model.belief_tracker.update(belief, obs, rng=self.rng)

        execution = ExecutionResult(
            plan_id=selected.get("plan_id", ""),
            actions_results=results,
            total_cost=round(total_cost, 2),
            successful=successful,
            failed_actions=failed,
        )

        wm_observations = []
        for res in results:
            action = next((a for a in actions if a.item_id == res["item_id"]), None)
            if action:
                wm_observations.append(
                    WorldModelObservation(
                        action_type=action.action_type,
                        item_id=action.item_id,
                        predicted_success_prob=action.estimated_success_prob,
                        actual_success=res["status"] == "BOOKED",
                        actual_cost=res.get("cost", action.estimated_cost),
                        reward=2.0 if res["status"] == "BOOKED" else -3.0,
                    ).to_dict()
                )

        output = {
            "status": "learning",
            "execution_result": execution.to_dict(),
            "observations": wm_observations,
            "belief_state": belief.to_dict(),
            "partial_observations": observations,
            "reflections": [
                self._reflection(
                    "executor",
                    f"Executed plan {selected.get('plan_id')}: successful={successful}, cost={total_cost:.2f}. "
                    f"Partial observations={len(observations)}.",
                )
            ],
            "logs": [self._log("executor", f"Executed plan {selected.get('plan_id')}")],
        }
        return output

    # ------------------------------------------------------------------
    # 6. Aprender del entorno real (reentrenamiento opcional)
    # ------------------------------------------------------------------
    def learn_from_observations_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        for obs_data in state.get("observations", []):
            obs = WorldModelObservation(**obs_data)
            self.world_model.update_from_observation(obs)
        # Reentrenar si hay suficientes observaciones nuevas
        if self.world_model.observations_since_train >= self.config.model.probabilistic.retrain_after:
            self.world_model.retrain()
        return {
            "status": "done",
            "world_model": self.world_model.to_dict(),
            "reflections": [
                self._reflection(
                    "monitor",
                    f"Updated world model with {len(state.get('observations', []))} observations. "
                    f"Retraining status: observations_since_train={self.world_model.observations_since_train}. "
                    f"Empirical estimates={len(self.world_model.estimates)}.",
                )
            ],
            "logs": [self._log("monitor", "World model updated/retrained")],
        }

    # ------------------------------------------------------------------
    # Finalizador
    # ------------------------------------------------------------------
    def finalize(self, state: Dict[str, Any]) -> Dict[str, Any]:
        status = state.get("status", "done")
        if status not in (
            "done",
            "awaiting_input",
            "awaiting_confirmation",
            "failed",
        ):
            status = "done"
        request = TravelPlanRequest.from_dict(state["request"])
        selected = state.get("selected_plan") or {}
        output = {
            "request_id": request.request_id,
            "user_id": request.user_id,
            "status": status,
            "selected_plan": selected,
            "candidates": state.get("candidates", []),
            "evaluations": state.get("evaluations", []),
            "execution_result": state.get("execution_result"),
            "world_model": state.get("world_model", {}),
            "belief_state": state.get("belief_state"),
            "partial_observations": state.get("partial_observations", []),
            "reflections": state.get("reflections", []),
            "logs": state.get("logs", []),
            "missing_info": state.get("missing_info", []),
            "safety_flags": state.get("safety_flags", []),
            "requires_confirmation": state.get("requires_confirmation", False),
        }
        return {"status": status, "final_output": output}


class CandidatePlanAdapter:
    """Helper para convertir dict -> CandidatePlan sin romper nodos."""

    def __init__(self, data: Dict[str, Any]) -> None:
        from models import CandidatePlan

        self.candidate = CandidatePlan(**data)

    def to_candidate(self):
        return self.candidate


class TransitionAdapter:
    """Genera una transición resumida a partir de un plan y una simulación."""

    def __init__(self, actions: List[Dict[str, Any]], sim: Dict[str, Any]) -> None:
        self.actions = actions
        self.sim = sim

    def to_transition(self):
        from models import Transition

        return Transition(
            prev_state={"actions": self.actions},
            action=self.actions[0] if self.actions else {},
            next_state=self.sim.get("outcome", {}),
            reward=self.sim.get("utility", 0.0),
            probability=1.0,
            info={"source": "simulated_rollout"},
        )
