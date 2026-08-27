"""World Model probabilístico para UC-265.

Combina:
- Simulador físico determinista del dominio de viajes.
- Estimaciones empíricas.
- Red neuronal o Proceso Gaussiano para predicción de transiciones/recompensas.
- Particle filter para entornos parcialmente observables.
- Persistencia SQLite y vector store.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config import AppConfig, ModelConfig, get_config
from models import (
    BeliefState,
    HiddenState,
    Observation,
    PlanAction,
    Transition,
    TravelPlanRequest,
    WorldModelObservation,
    WorldModelState,
    now_iso,
)
from probabilistic_model import (
    BeliefStateTracker,
    GPTransitionModel,
    NeuralTransitionModel,
)
from sqlite_store import SQLiteStore
from travel_world import TravelWorldSimulator
from vector_store import SimpleVectorStore


@dataclass
class EmpiricalEstimate:
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
            return 0.95
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
    """World model probabilístico con reentrenamiento y persistencia."""

    _lock = threading.Lock()

    def __init__(
        self,
        config: Optional[ModelConfig] = None,
        simulator: Optional[TravelWorldSimulator] = None,
        sqlite_store: Optional[SQLiteStore] = None,
        vector_store: Optional[SimpleVectorStore] = None,
        app_config: Optional[AppConfig] = None,
    ) -> None:
        self.app_config = app_config or get_config()
        self.config = config or self.app_config.model
        self.simulator = simulator or TravelWorldSimulator(self.app_config.world)
        self.sqlite = sqlite_store or SQLiteStore(self.config.storage.sqlite_path)
        self.vector_store = vector_store
        if self.vector_store is None and self.config.storage.use_vector_store:
            self.vector_store = SimpleVectorStore(
                dim=self.config.storage.vector_dim,
                path=self.config.storage.vector_store_path,
            )
        self.estimates: Dict[str, EmpiricalEstimate] = {}
        self.transitions: List[Dict[str, Any]] = []
        self.observations_since_train = 0
        self.belief_tracker = BeliefStateTracker(num_particles=100)

        if self.config.probabilistic.model_type == "neural":
            self.probabilistic_model = NeuralTransitionModel(self.config.probabilistic)
        elif self.config.probabilistic.model_type == "gp":
            self.probabilistic_model = GPTransitionModel(self.config.probabilistic)
        else:
            # hybrid: neural para éxito, GP para recompensa
            self.probabilistic_model = NeuralTransitionModel(self.config.probabilistic)

        # Cargar experiencias previas desde SQLite
        self._load_from_sqlite()

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
        rng = rng or np.random.default_rng()

        # Predicción probabilística + estimación empírica
        success_prob, reward_pred, uncertainty = self._predict_success_and_reward(
            state, action
        )

        # Incertidumbre como ruido adicional sobre la probabilidad
        noise = rng.normal(0, 0.05 + uncertainty * 0.2)
        success_prob = float(np.clip(success_prob + noise, 0.0, 1.0))

        if sample:
            success = rng.random() < success_prob
        else:
            success = success_prob >= 0.5

        next_state = state.copy()
        next_state.step += 1
        cost = action.estimated_cost
        reward = 0.0

        if success:
            next_state.itinerary.append({
                "step": action.step,
                "item_type": action.action_type,
                "id": action.item_id,
                "name": action.item_name,
                "details": action.details,
                "cost": cost,
                "status": "BOOKED",
                "source": "probabilistic_world_model",
            })
            next_state.total_cost += cost
            if next_state.remaining_budget is not None:
                next_state.remaining_budget -= cost
            reward = self._reward_for_success(action, next_state)
        else:
            reward = -3.0

        reward = 0.7 * reward + 0.3 * reward_pred

        transition = Transition(
            prev_state=state.to_dict(),
            action=action.to_dict(),
            next_state=next_state.to_dict(),
            reward=round(reward, 4),
            probability=round(success_prob, 4),
            info={
                "sampled_success": success,
                "predicted_success_prob": success_prob,
                "predicted_reward": reward_pred,
                "uncertainty": uncertainty,
                "model_type": self.config.probabilistic.model_type,
            },
        )
        return transition

    def _predict_success_and_reward(
        self, state: WorldModelState, action: PlanAction
    ) -> Tuple[float, float, float]:
        # Prior empírico
        empirical = self._get_estimate(action.action_type, action.item_id)
        emp_success = empirical.success_prob
        emp_reward = empirical.mean_reward

        # Modelo probabilístico (neural o GP)
        try:
            if isinstance(self.probabilistic_model, NeuralTransitionModel):
                p_success, r_pred, uncertainty = self.probabilistic_model.predict(
                    state.to_dict(), action.to_dict()
                )
            elif isinstance(self.probabilistic_model, GPTransitionModel):
                r_pred, uncertainty, p_success = self.probabilistic_model.predict(
                    state.to_dict(), action.to_dict()
                )
            else:
                p_success, r_pred, uncertainty = 0.95, 0.0, 1.0
        except Exception:
            p_success, r_pred, uncertainty = emp_success, emp_reward, 1.0

        # Combinar prior empírico y modelo probabilístico según evidencia
        if empirical.attempts == 0:
            return p_success, r_pred, uncertainty
        weight = min(0.8, empirical.attempts / 10.0)
        combined_success = weight * emp_success + (1 - weight) * p_success
        combined_reward = weight * emp_reward + (1 - weight) * r_pred
        return combined_success, combined_reward, uncertainty

    def rollout(
        self,
        state: WorldModelState,
        actions: List[PlanAction],
        rng: Optional[np.random.Generator] = None,
    ) -> Tuple[WorldModelState, float, bool, List[str]]:
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

        violations.extend(self._check_preferences(current))
        if violations:
            success = False
            total_reward -= len(violations) * 2.0

        return current, round(total_reward, 4), success, violations

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
            if prefs.get("hotel_chain") and prefs.get("hotel_chain") in action.item_name:
                reward += 1.5
            rating = action.details.get("rating", 0)
            reward += max(0, (rating - 3.0) * 0.5)
        return reward

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
    # Observabilidad parcial
    # ------------------------------------------------------------------
    def initialize_belief(self, request: TravelPlanRequest) -> BeliefState:
        return self.belief_tracker.initialize(request.to_state())

    def observe(self, item: Dict[str, Any], rng: Optional[np.random.Generator] = None) -> Observation:
        """Genera una observación ruidosa de un item (precio/disponibilidad/retraso)."""
        rng = rng or np.random.default_rng()
        noise = self.app_config.world.observation_noise
        observed_price = float(item.get("price_usd") or item.get("price_per_night_usd", 0.0))
        observed_price *= float(rng.normal(1.0, noise))
        return Observation(
            item_id=item.get("flight_id") or item.get("hotel_id", ""),
            observed_price=max(0, round(observed_price, 2)),
            observed_availability=max(0, int(item.get("seats_left") or item.get("rooms_left", 0)) + int(rng.normal(0, 1))),
            observed_delay=max(0.0, float(rng.exponential(15))),
            weather=rng.choice(["sunny", "cloudy", "rainy", "stormy"]),
            noise_level=noise,
        )

    # ------------------------------------------------------------------
    # Aprendizaje y reentrenamiento
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
        self.probabilistic_model.add_experience(
            state={},
            action={"action_type": observation.action_type, "item_id": observation.item_id},
            next_state={},
            reward=observation.reward,
            success=observation.actual_success,
        )
        self.observations_since_train += 1
        if self.observations_since_train >= self.config.probabilistic.retrain_after:
            self.retrain()
        self._persist_observation(observation)

    def retrain(self) -> None:
        """Reentrena el modelo probabilístico con todas las experiencias acumuladas."""
        self.probabilistic_model.fit()
        self.observations_since_train = 0

    def record_transition(self, transition: Transition) -> None:
        self.transitions.append(transition.to_dict())
        self.probabilistic_model.add_experience(
            transition.prev_state,
            transition.action,
            transition.next_state,
            transition.reward,
            transition.info.get("sampled_success", True),
        )
        if self.vector_store is not None:
            text = f"{transition.action.get('action_type')} {transition.action.get('item_id')} -> {transition.reward}"
            self.vector_store.add(text, metadata=transition.to_dict())
        if self.sqlite is not None and self.sqlite._path:
            self.sqlite.save_transition(transition.to_dict())

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------
    def _persist_observation(self, observation: WorldModelObservation) -> None:
        if self.sqlite is not None and self.sqlite._path:
            self.sqlite.save_observation(observation.to_dict())

    def _load_from_sqlite(self) -> None:
        if self.sqlite is None or not self.sqlite._path:
            return
        rows = self.sqlite.get_observations()
        for row in rows:
            obs = WorldModelObservation(**row)
            key = self._estimate_key(obs.action_type, obs.item_id)
            est = self.estimates.setdefault(key, EmpiricalEstimate())
            est.update(obs.actual_success, obs.actual_cost, obs.reward, lr=self.config.learning_rate)
            self.probabilistic_model.add_experience(
                {},
                {"action_type": obs.action_type, "item_id": obs.item_id},
                {},
                obs.reward,
                obs.actual_success,
            )

    def _get_estimate(self, action_type: str, item_id: str) -> EmpiricalEstimate:
        key = self._estimate_key(action_type, item_id)
        return self.estimates.get(key, EmpiricalEstimate())

    @staticmethod
    def _estimate_key(action_type: str, item_id: str) -> str:
        return f"{action_type}:{item_id}"

    def reset(self) -> None:
        with self._lock:
            self.estimates.clear()
            self.transitions.clear()
            self.observations_since_train = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "estimates": {k: v.to_dict() for k, v in self.estimates.items()},
            "num_transitions": len(self.transitions),
            "observations_since_train": self.observations_since_train,
            "model_type": self.config.probabilistic.model_type,
            "has_sqlite": bool(self.sqlite and self.sqlite._path),
            "has_vector_store": bool(self.vector_store),
        }
