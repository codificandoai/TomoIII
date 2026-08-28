"""Generador de datos sintéticos de viajes para entrenar el world model de UC-266."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config import AppConfig, get_config
from models import PlanAction, Transition, TravelPlanRequest, WorldModelState
from planner import PlanGenerator
from probabilistic_model import BeliefStateTracker
from travel_world import TravelWorldSimulator


class SyntheticDataGenerator:
    """Genera transiciones sintéticas (s, a, r, s') ejecutando planes simulados."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.simulator = TravelWorldSimulator(config.world)
        self.simulator_belief_tracker = BeliefStateTracker(num_particles=100)
        self.planner = PlanGenerator(self.simulator, config.model)
        self.rng = np.random.default_rng(config.world.seed + 999)

    def generate_request(self) -> TravelPlanRequest:
        origins = ["Madrid", "Barcelona", "Sevilla", "Valencia", "Bilbao"]
        destinations = ["Paris", "Londres", "Roma", "Berlin", "Lisboa", "Amsterdam"]
        airlines = ["AA", "IB", "LATAM", "AV", "UX", "Delta"]
        airlines = list(dict.fromkeys(airlines))  # keep unique
        origin = self.rng.choice(origins)
        destination = self.rng.choice([d for d in destinations if d != origin])
        dep = datetime(2026, 1, 1) + timedelta(days=int(self.rng.integers(0, 365)))
        ret = dep + timedelta(days=int(self.rng.integers(2, 10)))
        budget = float(self.rng.uniform(800, 4000))
        return TravelPlanRequest(
            origin=origin,
            destination=destination,
            departure_date=dep.date().isoformat(),
            return_date=ret.date().isoformat(),
            travelers=int(self.rng.integers(1, 5)),
            budget=budget,
            currency="USD",
            preferences={
                "airline": self.rng.choice(airlines),
                "direct_only": bool(self.rng.integers(0, 2)),
            },
            constraints=[],
            confirm_irreversible=False,
            user_id=f"synthetic-{self.rng.integers(0, 1000000)}",
        )

    def generate_transition(self) -> Optional[Dict[str, Any]]:
        request = self.generate_request()
        initial_state = WorldModelState(
            request_id=request.request_id,
            step=0,
            remaining_budget=request.budget,
            currency=request.currency,
            preferences=request.preferences,
            constraints=request.constraints,
        )
        # Inicializar belief state para que el modelo entrenado aprenda con features de creencia
        belief = self.simulator_belief_tracker.initialize(request.to_state())
        initial_state.belief_state = belief.to_dict()
        action_sequences, _ = self.planner.generate(request, num_plans=4)
        if not action_sequences:
            return None
        # Elegir una secuencia de acciones
        seq = action_sequences[self.rng.integers(0, len(action_sequences))]
        current = initial_state.copy()
        transitions: List[Dict[str, Any]] = []
        for action in seq:
            # Simular resultado real con algo de variabilidad oculta
            success = self._simulate_real_outcome(current, action)
            next_state = current.copy()
            next_state.step += 1
            reward = 0.0
            cost = action.estimated_cost
            if success:
                next_state.itinerary.append({
                    "step": action.step,
                    "item_type": action.action_type,
                    "id": action.item_id,
                    "name": action.item_name,
                    "details": action.details,
                    "cost": cost,
                    "status": "BOOKED",
                    "source": "synthetic_real_outcome",
                })
                next_state.total_cost += cost
                if next_state.remaining_budget is not None:
                    next_state.remaining_budget -= cost
                reward = self._reward_for_success(action, next_state)
            else:
                reward = -3.0
            transition = Transition(
                prev_state=current.to_dict(),
                action=action.to_dict(),
                next_state=next_state.to_dict(),
                reward=round(reward, 4),
                probability=1.0 if success else 0.0,
                info={"source": "synthetic", "real_success": success},
            )
            transitions.append(transition.to_dict())
            if not success:
                break
            current = next_state
        # Devolvemos la trayectoria completa como lista; el entrenador puede
        # usar cada transición individualmente.
        return {
            "request": request.to_state(),
            "trajectory": transitions,
        }

    def generate_batch(
        self, n: int = 1000
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Genera N trayectorias y devuelve (transitions, observations)."""
        transitions: List[Dict[str, Any]] = []
        observations: List[Dict[str, Any]] = []
        generated = 0
        attempts = 0
        while generated < n and attempts < n * 3:
            attempts += 1
            result = self.generate_transition()
            if not result:
                continue
            generated += 1
            for t in result["trajectory"]:
                transitions.append(t)
                action = t.get("action", {})
                observations.append({
                    "action_type": action.get("action_type", ""),
                    "item_id": action.get("item_id", ""),
                    "predicted_success_prob": action.get("estimated_success_prob", 0.95),
                    "actual_success": t.get("info", {}).get("real_success", True),
                    "actual_cost": action.get("estimated_cost", 0.0),
                    "reward": t.get("reward", 0.0),
                })
        return transitions, observations

    def _simulate_real_outcome(
        self, state: WorldModelState, action: PlanAction
    ) -> bool:
        # Probabilidad base de éxito; se reduce si el costo supera el presupuesto
        if state.remaining_budget is not None and action.estimated_cost > state.remaining_budget:
            return False
        base_prob = 0.92
        if action.action_type == "hotel":
            rating = action.details.get("rating", 3.0)
            base_prob -= max(0, (5 - rating) * 0.05)
        if action.details.get("airline") and action.details.get("airline") != state.preferences.get("airline"):
            base_prob -= 0.02
        noise = self.rng.normal(0, 0.05)
        return (base_prob + noise) > 0.5

    def _reward_for_success(self, action: PlanAction, state: WorldModelState) -> float:
        reward = 2.0
        prefs = state.preferences
        if action.action_type == "flight":
            airline = action.details.get("airline", "")
            if airline and prefs.get("airline") == airline:
                reward += 2.0
            if action.details.get("direct"):
                reward += 1.0
        if action.action_type == "hotel":
            rating = action.details.get("rating", 0)
            reward += max(0, (rating - 3.0) * 0.5)
        return reward
