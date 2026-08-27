"""World Model para UC-264: mantiene un modelo interno del entorno de viajes.

Predice transiciones (acción -> estado siguiente + recompensa) y aprende de
observaciones reales para refinar esas predicciones.
"""
from __future__ import annotations

import copy
import json
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config import AppConfig, ModelConfig, get_config
from models import (
    PlanAction,
    Transition,
    TravelPlanRequest,
    WorldModelObservation,
    WorldModelState,
    now_iso,
)
from travel_world import TravelWorldSimulator


@dataclass
class EmpiricalEstimate:
    """Estimación empírica de éxito para una acción."""

    attempts: int = 0
    successes: int = 0
    mean_cost: float = 0.0
    mean_reward: float = 0.0
    last_updated: str = field(default_factory=now_iso)

    def update(self, success: bool, cost: float, reward: float, lr: float = 0.2) -> None:
        self.attempts += 1
        if success:
            self.successes += 1
        if self.attempts == 1:
            self.mean_cost = cost
            self.mean_reward = reward
        else:
            self.mean_cost = (1 - lr) * self.mean_cost + lr * cost
            self.mean_reward = (1 - lr) * self.mean_reward + lr * reward
        self.last_updated = now_iso()

    @property
    def success_prob(self) -> float:
        if self.attempts == 0:
            return 0.95  # default optimista antes de evidencia
        return self.successes / self.attempts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempts": self.attempts,
            "successes": self.successes,
            "success_prob": self.success_prob,
            "mean_cost": self.mean_cost,
            "mean_reward": self.mean_reward,
            "last_updated": self.last_updated,
        }


class TravelWorldModel:
    """Modelo interno del entorno de viajes.

    Combina un simulador físico (TravelWorldSimulator) con estimaciones
    empíricas aprendidas de observaciones previas.
    """

    _lock = threading.Lock()

    def __init__(
        self,
        config: Optional[ModelConfig] = None,
        simulator: Optional[TravelWorldSimulator] = None,
        memory_path: Optional[str] = None,
    ) -> None:
        self.config = config or get_config().model
        self.simulator = simulator or TravelWorldSimulator(get_config().world)
        self.memory_path = memory_path or ""
        self.estimates: Dict[str, EmpiricalEstimate] = {}
        self.transitions: List[Transition] = []
        if self.memory_path and os.path.exists(self.memory_path):
            self._load_from_disk()

    # ------------------------------------------------------------------
    # Predicción
    # ------------------------------------------------------------------
    def predict_transition(
        self,
        state: WorldModelState,
        action: PlanAction,
        sample: bool = False,
        rng: Optional[np.random.Generator] = None,
    ) -> Transition:
        """Predice la transición (s, a, s', r, p)."""
        rng = rng or np.random.default_rng()
        estimate = self._get_estimate(action.action_type, action.item_id)
        base_prob = estimate.success_prob
        noise = rng.normal(0, 0.05)
        success_prob = float(np.clip(base_prob + noise, 0.0, 1.0))

        if sample:
            success = rng.random() < success_prob
        else:
            success = success_prob >= 0.5

        next_state = state.copy()
        next_state.step += 1
        reward = 0.0
        cost = action.estimated_cost

        if success:
            itinerary_item = {
                "step": action.step,
                "item_type": action.action_type,
                "id": action.item_id,
                "name": action.item_name,
                "details": action.details,
                "cost": cost,
                "status": "BOOKED",
                "source": "world_model_prediction",
            }
            next_state.itinerary.append(itinerary_item)
            next_state.total_cost += cost
            if next_state.remaining_budget is not None:
                next_state.remaining_budget -= cost
            reward = self._reward_for_success(action, next_state)
        else:
            reward = self._reward_for_failure(action, next_state)

        transition = Transition(
            prev_state=state.to_dict(),
            action=action.to_dict(),
            next_state=next_state.to_dict(),
            reward=round(reward, 4),
            probability=round(success_prob, 4),
            info={
                "sampled_success": success,
                "predicted_success_prob": base_prob,
                "empirical_estimate": estimate.to_dict(),
            },
        )
        return transition

    def rollout(
        self,
        state: WorldModelState,
        actions: List[PlanAction],
        rng: Optional[np.random.Generator] = None,
    ) -> Tuple[WorldModelState, float, bool, List[str]]:
        """Simula una trayectoria completa y devuelve estado final, recompensa acumulada,
        éxito global y restricciones violadas."""
        rng = rng or np.random.default_rng()
        current = state.copy()
        total_reward = 0.0
        success = True
        violations: List[str] = []

        for action in actions:
            if current.remaining_budget is not None and action.estimated_cost > current.remaining_budget:
                violations.append(f"Budget exceeded by action {action.action_id}")
                success = False
                total_reward -= 5.0
                break
            transition = self.predict_transition(current, action, sample=True, rng=rng)
            if not transition.info.get("sampled_success", True):
                success = False
            current = WorldModelState(**transition.next_state)
            total_reward += transition.reward

        # Penalización por restricciones de preferencias
        violations.extend(self._check_preferences(current))
        if violations:
            success = False
            total_reward -= len(violations) * 2.0

        return current, round(total_reward, 4), success, violations

    def _reward_for_success(self, action: PlanAction, state: WorldModelState) -> float:
        reward = 2.0  # base por reservar exitosamente
        prefs = state.preferences
        if action.action_type == "flight":
            airline = action.details.get("airline", "")
            if airline and prefs.get("airline") == airline:
                reward += 2.0
            if action.details.get("direct"):
                reward += 1.0
        if action.action_type == "hotel":
            if prefs.get("hotel_chain") and prefs.get("hotel_chain") in action.item_name:
                reward += 1.5
            rating = action.details.get("rating", 0)
            reward += max(0, (rating - 3.0) * 0.5)
        return reward

    def _reward_for_failure(self, action: PlanAction, state: WorldModelState) -> float:
        return -3.0

    def _check_preferences(self, state: WorldModelState) -> List[str]:
        violations = []
        prefs = state.preferences
        budget = state.remaining_budget
        if budget is not None and budget < 0:
            violations.append("Budget exceeded")
        if prefs.get("direct_only"):
            for item in state.itinerary:
                if item.get("item_type") == "flight" and not item.get("details", {}).get("direct"):
                    violations.append("Non-direct flight selected")
        return violations

    # ------------------------------------------------------------------
    # Aprendizaje
    # ------------------------------------------------------------------
    def update_from_observation(self, observation: WorldModelObservation) -> None:
        key = self._estimate_key(observation.action_type, observation.item_id)
        estimate = self.estimates.setdefault(key, EmpiricalEstimate())
        estimate.update(
            success=observation.actual_success,
            cost=observation.actual_cost,
            reward=observation.reward,
            lr=self.config.learning_rate,
        )
        self._persist()

    def _get_estimate(self, action_type: str, item_id: str) -> EmpiricalEstimate:
        key = self._estimate_key(action_type, item_id)
        return self.estimates.get(key, EmpiricalEstimate())

    @staticmethod
    def _estimate_key(action_type: str, item_id: str) -> str:
        return f"{action_type}:{item_id}"

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------
    def _persist(self) -> None:
        if not self.memory_path:
            return
        try:
            os.makedirs(os.path.dirname(self.memory_path) or ".", exist_ok=True)
            data = {
                "estimates": {k: v.to_dict() for k, v in self.estimates.items()},
                "transitions": [t.to_dict() for t in self.transitions[-500:]],
            }
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _load_from_disk(self) -> None:
        try:
            with open(self.memory_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.get("estimates", {}).items():
                est = EmpiricalEstimate()
                est.attempts = v.get("attempts", 0)
                est.successes = v.get("successes", 0)
                est.mean_cost = v.get("mean_cost", 0.0)
                est.mean_reward = v.get("mean_reward", 0.0)
                est.last_updated = v.get("last_updated", now_iso())
                self.estimates[k] = est
        except (json.JSONDecodeError, OSError):
            self.estimates = {}

    def reset(self) -> None:
        with self._lock:
            self.estimates.clear()
            self.transitions.clear()
            if self.memory_path and os.path.exists(self.memory_path):
                try:
                    os.remove(self.memory_path)
                except OSError:
                    pass

    def to_dict(self) -> Dict[str, Any]:
        return {
            "estimates": {k: v.to_dict() for k, v in self.estimates.items()},
            "num_transitions": len(self.transitions),
            "config": {
                "num_candidate_plans": self.config.num_candidate_plans,
                "mc_simulations_per_plan": self.config.mc_simulations_per_plan,
                "learning_rate": self.config.learning_rate,
            },
        }
