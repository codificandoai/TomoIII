"""Nodos LangGraph del sistema model-based multi-agente para UC-264."""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

import numpy as np

from config import AppConfig
from critic import PlanCritic
from models import (
    ExecutionResult,
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
    """Nodos del workflow de planificación basada en modelo."""

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
    # 1. Entrada y construcción del world model
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

        return {
            "status": "generating",
            "world_model": self.world_model.to_dict(),
            "reflections": [
                self._reflection(
                    "world_model",
                    f"Built world model for {request.origin}->{request.destination}. "
                    f"Loaded {len(self.world_model.estimates)} empirical estimates.",
                )
            ],
            "logs": [self._log("world_model", f"Built model for request {request.request_id}")],
        }

    # ------------------------------------------------------------------
    # 2. Generar candidatos
    # ------------------------------------------------------------------
    def generate_candidates_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        request = TravelPlanRequest.from_dict(state["request"])
        action_sequences, meta = self.planner.generate(request)
        candidates = [
            {"plan_id": f"plan-{i+1:03d}", "strategy": "TBD", "actions": [a.to_dict() for a in seq]}
            for i, seq in enumerate(action_sequences)
        ]
        return {
            "status": "simulating",
            "candidates": candidates,
            "reflections": [
                self._reflection(
                    "planner",
                    f"Generated {len(candidates)} candidate plans using strategies: {meta.get('strategies')}",
                )
            ],
            "logs": [self._log("planner", f"Generated {len(candidates)} candidates")],
        }

    # ------------------------------------------------------------------
    # 3. Simular candidatos
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
        return {
            "status": "evaluating",
            "candidates": [c.to_dict() for c in evaluated],
            "reflections": [
                self._reflection(
                    "simulator",
                    f"Simulated {len(evaluated)} candidate plans with {self.config.model.mc_simulations_per_plan} rollouts each.",
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

        execution = ExecutionResult(
            plan_id=selected.get("plan_id", ""),
            actions_results=results,
            total_cost=round(total_cost, 2),
            successful=successful,
            failed_actions=failed,
        )

        observations = []
        for res in results:
            action = next((a for a in actions if a.item_id == res["item_id"]), None)
            if action:
                observations.append(
                    WorldModelObservation(
                        action_type=action.action_type,
                        item_id=action.item_id,
                        predicted_success_prob=action.estimated_success_prob,
                        actual_success=res["status"] == "BOOKED",
                        actual_cost=res.get("cost", action.estimated_cost),
                        reward=2.0 if res["status"] == "BOOKED" else -3.0,
                    ).to_dict()
                )

        return {
            "status": "learning",
            "execution_result": execution.to_dict(),
            "observations": observations,
            "reflections": [
                self._reflection(
                    "executor",
                    f"Executed plan {selected.get('plan_id')}: successful={successful}, cost={total_cost:.2f}",
                )
            ],
            "logs": [self._log("executor", f"Executed plan {selected.get('plan_id')}")],
        }

    # ------------------------------------------------------------------
    # 6. Aprender del entorno real
    # ------------------------------------------------------------------
    def learn_from_observations_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        for obs_data in state.get("observations", []):
            obs = WorldModelObservation(**obs_data)
            self.world_model.update_from_observation(obs)
        return {
            "status": "done",
            "world_model": self.world_model.to_dict(),
            "reflections": [
                self._reflection(
                    "monitor",
                    f"Updated world model with {len(state.get('observations', []))} observations. "
                    f"Now {len(self.world_model.estimates)} empirical estimates.",
                )
            ],
            "logs": [self._log("monitor", "World model updated")],
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

        self.data = data
        self.candidate = CandidatePlan(**data)

    def to_candidate(self):
        return self.candidate
