"""World Model probabilístico para UC-292.

Combina:
- Historial de precios por símbolo.
- Estimaciones empíricas por (símbolo, side).
- Red neuronal / GP para predicción de transiciones/recompensas.
- Particle filter para estados parcialmente observables.
- Persistencia SQLite y vector store.
"""
from __future__ import annotations

import math
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config import AppConfig, ModelConfig, get_config
from models import (
    AgentAction,
    BeliefState,
    Observation,
    Transition,
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
            return 0.5
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


class TradingWorldModel:
    """World model probabilístico para trading con reentrenamiento y persistencia."""

    _lock = threading.Lock()

    def __init__(
        self,
        config: Optional[ModelConfig] = None,
        sqlite_store: Optional[SQLiteStore] = None,
        vector_store: Optional[SimpleVectorStore] = None,
        app_config: Optional[AppConfig] = None,
    ) -> None:
        self.app_config = app_config or get_config()
        self.config = config or self.app_config.model
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
        self.last_uncertainty = 1.0
        self.price_history: Dict[str, deque[float]] = {}
        self.prediction_errors: deque[float] = deque(
            maxlen=max(1, self.config.probabilistic.prediction_error_window)
        )
        self.belief_tracker = BeliefStateTracker(num_particles=100)

        if self.config.probabilistic.model_type == "neural":
            self.probabilistic_model = NeuralTransitionModel(self.config.probabilistic)
        elif self.config.probabilistic.model_type == "gp":
            self.probabilistic_model = GPTransitionModel(self.config.probabilistic)
        else:
            self.probabilistic_model = NeuralTransitionModel(self.config.probabilistic)

        self._load_from_sqlite()

    # ------------------------------------------------------------------
    # Predicción
    # ------------------------------------------------------------------
    def predict_transition(
        self,
        state: WorldModelState,
        action: AgentAction,
        sample: bool = False,
        rng: Optional[np.random.Generator] = None,
    ) -> Transition:
        rng = rng or np.random.default_rng()
        symbol = action.symbol
        side = action.side.upper()
        price = state.price
        position = state.position
        cash = state.cash
        qty = action.quantity

        success_prob, reward_pred, uncertainty = self._predict_success_and_reward(
            state.to_dict(), action.to_dict(), state.features.get("belief")
        )
        self.last_uncertainty = uncertainty

        # Predecir retorno del siguiente tick con el modelo neuronal o empírico
        predicted_ret, ret_uncertainty = self._predict_next_return(
            state.to_dict(), action.to_dict(), state.features.get("belief")
        )
        empirical_ret = self._estimate_return(symbol)
        # Combinar predicción del modelo con prior empírico
        if self._has_trained_return_model():
            ret = 0.7 * predicted_ret + 0.3 * empirical_ret
        else:
            ret = empirical_ret

        vol = state.features.get("volatility", 0.0)
        next_price = price * (1.0 + ret + rng.normal(0, max(1e-6, vol)))
        next_price = max(0.01, next_price)

        if sample:
            success = rng.random() < success_prob
        else:
            success = success_prob >= 0.5

        next_state = state.copy()
        next_state.step += 1
        next_state.price = round(next_price, 4)
        reward = reward_pred

        if success and side == "BUY":
            notional = qty * next_price
            if notional <= cash:
                next_state.position = round(position + qty, 6)
                next_state.cash = round(cash - notional, 4)
        elif success and side == "SELL":
            if qty <= position:
                proceeds = qty * next_price
                next_state.position = round(position - qty, 6)
                next_state.cash = round(cash + proceeds, 4)

        next_state.portfolio_value = round(
            next_state.cash + next_state.position * next_price, 4
        )
        reward = self._normalize_reward(next_state.portfolio_value - state.portfolio_value)
        reward = 0.7 * reward + 0.3 * reward_pred

        return Transition(
            prev_state=state.to_dict(),
            action=action.to_dict(),
            next_state=next_state.to_dict(),
            reward=round(reward, 6),
            probability=round(success_prob, 6),
            info={
                "sampled_success": success,
                "predicted_success_prob": success_prob,
                "predicted_reward": reward_pred,
                "predicted_return": round(ret, 6),
                "predicted_next_price": round(next_price, 4),
                "uncertainty": uncertainty,
                "model_type": self.config.probabilistic.model_type,
                "symbol": symbol,
                "side": side,
            },
        )

    def _predict_success_and_reward(
        self,
        state: Dict[str, Any],
        action: Dict[str, Any],
        belief: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, float, float]:
        empirical = self._get_estimate(action.get("symbol", ""), action.get("side", "HOLD"))
        emp_success = empirical.success_prob
        emp_reward = empirical.mean_reward

        try:
            if isinstance(self.probabilistic_model, NeuralTransitionModel):
                p_success, r_pred, uncertainty = self.probabilistic_model.predict(
                    state, action, belief
                )
            elif isinstance(self.probabilistic_model, GPTransitionModel):
                r_pred, uncertainty, p_success = self.probabilistic_model.predict(
                    state, action, belief
                )
            else:
                p_success, r_pred, uncertainty = 0.5, 0.0, 1.0
        except Exception:
            p_success, r_pred, uncertainty = emp_success, emp_reward, 1.0

        if empirical.attempts == 0:
            return p_success, r_pred, uncertainty
        weight = min(0.8, empirical.attempts / 10.0)
        combined_success = weight * emp_success + (1 - weight) * p_success
        combined_reward = weight * emp_reward + (1 - weight) * r_pred
        return combined_success, combined_reward, uncertainty

    def rollout(
        self,
        state: WorldModelState,
        actions: List[AgentAction],
        rng: Optional[np.random.Generator] = None,
    ) -> Tuple[WorldModelState, float, bool, List[str]]:
        rng = rng or np.random.default_rng()
        current = state.copy()
        total_reward = 0.0
        success = True
        violations: List[str] = []
        initial_value = current.portfolio_value

        for action in actions:
            if current.done:
                violations.append("Episode already done")
                success = False
                break
            transition = self.predict_transition(current, action, sample=True, rng=rng)
            if not transition.info.get("sampled_success", True):
                success = False
            current = WorldModelState(**transition.next_state)
            total_reward += transition.reward
            if current.portfolio_value < initial_value * 0.95:
                violations.append("Drawdown limit exceeded")
                current.done = True

        return current, round(total_reward, 6), success, violations

    def _estimate_return(self, symbol: str) -> float:
        hist = self.price_history.get(symbol, deque(maxlen=50))
        if len(hist) < 2:
            return 0.0
        arr = list(hist)
        return float(np.mean(np.diff(arr) / np.array(arr[:-1])))

    def _normalize_reward(self, raw_pnl: float) -> float:
        return math.tanh(raw_pnl / 1_000.0)

    def _predict_next_return(
        self,
        state: Dict[str, Any],
        action: Dict[str, Any],
        belief: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, float]:
        """Predice el retorno del siguiente tick con el modelo neuronal."""
        if isinstance(self.probabilistic_model, NeuralTransitionModel):
            return self.probabilistic_model.predict_next_return(state, action, belief)
        return 0.0, 1.0

    def _has_trained_return_model(self) -> bool:
        return (
            isinstance(self.probabilistic_model, NeuralTransitionModel)
            and self.probabilistic_model._trained
            and len(self.probabilistic_model._y_next_return)
            >= self.config.probabilistic.min_samples_to_train
            and len(set(self.probabilistic_model._y_next_return)) > 1
        )

    def predict_next_price(
        self,
        symbol: str,
        current_price: float,
        features: Optional[Dict[str, Any]] = None,
        action: Optional[AgentAction] = None,
    ) -> Dict[str, float]:
        """Predice el siguiente tick price y reporta incertidumbre."""
        action = action or AgentAction(symbol=symbol, side="HOLD", quantity=0.0, price=current_price)
        state = WorldModelState(
            symbol=symbol,
            price=current_price,
            features=features or {},
        ).to_dict()
        predicted_ret, uncertainty = self._predict_next_return(
            state, action.to_dict(), (features or {}).get("belief")
        )
        empirical_ret = self._estimate_return(symbol)
        ret = predicted_ret if self._has_trained_return_model() else empirical_ret
        predicted_price = max(0.01, current_price * (1.0 + ret))
        return {
            "symbol": symbol,
            "current_price": round(current_price, 4),
            "predicted_next_price": round(predicted_price, 4),
            "predicted_return": round(ret, 6),
            "model_return": round(predicted_ret, 6),
            "empirical_return": round(empirical_ret, 6),
            "uncertainty": round(uncertainty, 6),
            "model_type": self.config.probabilistic.model_type,
        }

    def update_from_tick(
        self,
        symbol: str,
        current_price: float,
        next_price: float,
        action: Optional[AgentAction] = None,
        features: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Retroalimenta el world model con un par de ticks consecutivos reales."""
        self.update_price_history(symbol, current_price)
        self.update_price_history(symbol, next_price)
        action = action or AgentAction(symbol=symbol, side="HOLD", quantity=0.0, price=current_price)
        state = WorldModelState(symbol=symbol, price=current_price, features=features or {}).to_dict()
        next_state = WorldModelState(symbol=symbol, price=next_price, features=features or {}).to_dict()
        actual_return = (next_price - current_price) / current_price if current_price > 0 else 0.0

        self.probabilistic_model.add_experience(
            state=state,
            action=action.to_dict(),
            next_state=next_state,
            reward=actual_return,
            success=True,
            next_return=actual_return,
        )
        self.observations_since_train += 1
        if self._should_retrain():
            self.retrain()

    # ------------------------------------------------------------------
    # Observabilidad parcial
    # ------------------------------------------------------------------
    def initialize_belief(self, seed_text: str = "42") -> BeliefState:
        return self.belief_tracker.initialize(seed_text)

    def observe(self, price: float, volatility: float = 0.0) -> Observation:
        return Observation(
            item_id="market",
            observed_price=max(0.01, round(price, 4)),
            observed_volatility=round(volatility, 6),
            observed_volume=0.0,
            noise_level=0.05,
        )

    def update_belief(
        self,
        belief: BeliefState,
        price: float,
        volatility: float = 0.0,
        rng: Optional[np.random.Generator] = None,
    ) -> BeliefState:
        obs = self.observe(price, volatility)
        return self.belief_tracker.update(belief, obs, rng=rng)

    # ------------------------------------------------------------------
    # Aprendizaje y reentrenamiento
    # ------------------------------------------------------------------
    def update_price_history(self, symbol: str, price: float) -> None:
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=200)
        self.price_history[symbol].append(float(price))

    def update_from_observation(self, observation: WorldModelObservation) -> None:
        key = self._estimate_key(observation.symbol, observation.action_type)
        estimate = self.estimates.setdefault(key, EmpiricalEstimate())
        estimate.update(
            success=observation.actual_success,
            cost=observation.actual_cost,
            reward=observation.reward,
            lr=self.config.learning_rate,
        )
        self.probabilistic_model.add_experience(
            state={},
            action={"symbol": observation.symbol, "side": observation.action_type},
            next_state={},
            reward=observation.reward,
            success=observation.actual_success,
        )
        self.observations_since_train += 1
        pred = observation.predicted_success_prob
        actual = 1.0 if observation.actual_success else 0.0
        self.prediction_errors.append(abs(pred - actual))
        if self._should_retrain():
            self.retrain()
        self._persist_observation(observation)

    def _should_retrain(self) -> bool:
        cfg = self.config.probabilistic
        if self.observations_since_train >= cfg.retrain_after:
            return True
        if (
            isinstance(self.probabilistic_model, GPTransitionModel)
            and self.last_uncertainty > cfg.uncertainty_retrain_threshold
        ):
            return True
        if len(self.prediction_errors) >= 2:
            avg_error = sum(self.prediction_errors) / len(self.prediction_errors)
            if avg_error > cfg.prediction_error_retrain_threshold:
                return True
        return False

    def retrain(self) -> None:
        self.probabilistic_model.fit()
        self.observations_since_train = 0

    def record_transition(self, transition: Transition) -> None:
        self.transitions.append(transition.to_dict())
        belief = transition.prev_state.get("features", {}).get("belief")
        self.probabilistic_model.add_experience(
            transition.prev_state,
            transition.action,
            transition.next_state,
            transition.reward,
            transition.info.get("sampled_success", True),
            belief=belief,
        )
        if self.vector_store is not None:
            text = (
                f"{transition.action.get('symbol', '')} "
                f"{transition.action.get('side', '')} -> {transition.reward}"
            )
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
            key = self._estimate_key(obs.symbol, obs.action_type)
            est = self.estimates.setdefault(key, EmpiricalEstimate())
            est.update(obs.actual_success, obs.actual_cost, obs.reward, lr=self.config.learning_rate)
            self.probabilistic_model.add_experience(
                {},
                {"symbol": obs.symbol, "side": obs.action_type},
                {},
                obs.reward,
                obs.actual_success,
            )

    def _get_estimate(self, symbol: str, side: str) -> EmpiricalEstimate:
        key = self._estimate_key(symbol, side)
        return self.estimates.get(key, EmpiricalEstimate())

    @staticmethod
    def _estimate_key(symbol: str, side: str) -> str:
        return f"{symbol}:{side}".upper()

    def reset(self) -> None:
        with self._lock:
            self.estimates.clear()
            self.transitions.clear()
            self.price_history.clear()
            self.observations_since_train = 0
            self.prediction_errors.clear()

    def to_dict(self) -> Dict[str, Any]:
        avg_error = (
            round(sum(self.prediction_errors) / len(self.prediction_errors), 4)
            if self.prediction_errors
            else 0.0
        )
        return {
            "estimates": {k: v.to_dict() for k, v in self.estimates.items()},
            "num_transitions": len(self.transitions),
            "observations_since_train": self.observations_since_train,
            "last_uncertainty": round(self.last_uncertainty, 4),
            "avg_prediction_error": avg_error,
            "prediction_error_window": self.config.probabilistic.prediction_error_window,
            "model_type": self.config.probabilistic.model_type,
            "has_sqlite": bool(self.sqlite and self.sqlite._path),
            "has_vector_store": bool(self.vector_store),
            "symbols": list(self.price_history.keys()),
        }
