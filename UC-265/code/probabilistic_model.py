"""Modelos probabilísticos de transición y recompensa para UC-265.

Incluye:
- Red neuronal (MLPRegressor) para predecir next-state features y reward.
- Proceso Gaussiano (GaussianProcessRegressor) con incertidumbre.
- Particle filter para mantener estado de creencia en entornos parcialmente observables.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel
from sklearn.neural_network import MLPRegressor

from config import AppConfig, ProbabilisticModelConfig, get_config
from models import BeliefState, HiddenState, Observation


class StateEncoder:
    """Codifica estados y acciones en vectores numéricos fijos."""

    def __init__(self, dim: int = 16) -> None:
        self.dim = dim
        self._action_types = {"flight": 0, "hotel": 1, "activity": 2, "noop": 3}

    def encode_state(self, state: Dict[str, Any]) -> np.ndarray:
        rng = np.random.default_rng(self._hash(str(state)))
        vec = rng.random(self.dim)
        # Añadir features reales cuando existan
        budget = state.get("remaining_budget") or state.get("total_cost") or 0.0
        vec[0] = float(budget) / 10000.0
        step = state.get("step", 0)
        vec[1] = step / 10.0
        return self._normalize(vec)

    def encode_action(self, action: Dict[str, Any]) -> np.ndarray:
        rng = np.random.default_rng(self._hash(str(action)))
        vec = rng.random(self.dim)
        atype = self._action_types.get(action.get("action_type", "noop"), 3)
        vec[0] = atype / 3.0
        cost = action.get("estimated_cost", 0.0)
        vec[1] = cost / 1000.0
        return self._normalize(vec)

    def encode_belief(self, belief: Optional[Dict[str, Any]]) -> np.ndarray:
        """Resume el belief state en features numéricas fijas.

        Devuelve: [mean_market_pressure, std_market_pressure, p_sunny, p_cloudy, p_rainy, p_stormy]
        """
        if not belief:
            return np.zeros(6)
        particles = belief.get("particles", [])
        if not particles:
            return np.zeros(6)
        market_pressures = [p.get("market_pressure", 0.0) for p in particles]
        mean_mp = float(np.mean(market_pressures))
        std_mp = float(np.std(market_pressures)) if len(market_pressures) > 1 else 0.0
        weathers = [p.get("weather_condition", "unknown") for p in particles]
        total = len(weathers)
        counts = {"sunny": 0, "cloudy": 0, "rainy": 0, "stormy": 0}
        for w in weathers:
            if w in counts:
                counts[w] += 1
        probs = [counts[k] / total for k in ("sunny", "cloudy", "rainy", "stormy")]
        return np.array([mean_mp, std_mp] + probs, dtype=np.float64)

    def encode_transition(
        self,
        state: Dict[str, Any],
        action: Dict[str, Any],
        belief: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        s = self.encode_state(state)
        a = self.encode_action(action)
        b = self.encode_belief(belief)
        return np.concatenate([s, a, b])

    @staticmethod
    def _hash(text: str) -> int:
        import hashlib
        return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)

    @staticmethod
    def _normalize(vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        return vec if norm == 0 else vec / norm


class NeuralTransitionModel:
    """Red neuronal que predice (delta_state_features, reward, success_prob)."""

    def __init__(self, config: ProbabilisticModelConfig) -> None:
        self.config = config
        self.encoder = StateEncoder(config.embedding_dim)
        self.belief_dim = 6
        input_dim = config.embedding_dim * 2 + self.belief_dim
        self.model_success = MLPRegressor(
            hidden_layer_sizes=config.hidden_layers,
            max_iter=config.max_iter,
            random_state=42,
            early_stopping=False,
        )
        self.model_reward = MLPRegressor(
            hidden_layer_sizes=config.hidden_layers,
            max_iter=config.max_iter,
            random_state=43,
            early_stopping=False,
        )
        self._trained = False
        self._X: List[np.ndarray] = []
        self._y_success: List[float] = []
        self._y_reward: List[float] = []

    def add_experience(
        self,
        state: Dict[str, Any],
        action: Dict[str, Any],
        next_state: Dict[str, Any],
        reward: float,
        success: bool,
        belief: Optional[Dict[str, Any]] = None,
    ) -> None:
        x = self.encoder.encode_transition(state, action, belief)
        self._X.append(x)
        self._y_success.append(1.0 if success else 0.0)
        self._y_reward.append(reward)

    def fit(self) -> None:
        if len(self._X) < self.config.min_samples_to_train:
            return
        X = np.array(self._X)
        self.model_success.fit(X, np.array(self._y_success))
        self.model_reward.fit(X, np.array(self._y_reward))
        self._trained = True

    def predict(
        self,
        state: Dict[str, Any],
        action: Dict[str, Any],
        belief: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, float, float]:
        """Devuelve (success_prob, reward, uncertainty)."""
        if not self._trained:
            return 0.95, 0.0, 1.0  # alta incertidumbre por defecto
        x = self.encoder.encode_transition(state, action, belief).reshape(1, -1)
        success_prob = float(np.clip(self.model_success.predict(x)[0], 0.0, 1.0))
        reward = float(self.model_reward.predict(x)[0])
        # Incertidumbre proxy: inversamente proporcional al tamaño del dataset
        uncertainty = max(0.1, 1.0 / (1.0 + len(self._X) / 20.0))
        return success_prob, reward, uncertainty


class GPTransitionModel:
    """Proceso Gaussiano que predice recompensa con estimación de incertidumbre."""

    def __init__(self, config: ProbabilisticModelConfig) -> None:
        self.config = config
        self.encoder = StateEncoder(config.embedding_dim)
        kernel = RBF(length_scale=1.0, length_scale_bounds=(1e-2, 10.0)) + WhiteKernel(
            noise_level=0.1, noise_level_bounds=(1e-10, 1.0)
        )
        self.model = GaussianProcessRegressor(
            kernel=kernel,
            alpha=config.gp_alpha,
            random_state=42,
            normalize_y=True,
            n_restarts_optimizer=2,
        )
        self._trained = False
        self._X: List[np.ndarray] = []
        self._y: List[float] = []

    def add_experience(
        self,
        state: Dict[str, Any],
        action: Dict[str, Any],
        next_state: Dict[str, Any],
        reward: float,
        success: bool,
        belief: Optional[Dict[str, Any]] = None,
    ) -> None:
        x = self.encoder.encode_transition(state, action, belief)
        self._X.append(x)
        self._y.append(reward)

    def fit(self) -> None:
        if len(self._X) < self.config.min_samples_to_train:
            return
        X = np.array(self._X)
        y = np.array(self._y)
        if len(np.unique(y)) < 2:
            return
        self.model.fit(X, y)
        self._trained = True

    def predict(
        self,
        state: Dict[str, Any],
        action: Dict[str, Any],
        belief: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, float, float]:
        """Devuelve (reward_pred, std, success_prob_proxy)."""
        if not self._trained:
            return 0.0, 1.0, 0.95
        x = self.encoder.encode_transition(state, action, belief).reshape(1, -1)
        mean, std = self.model.predict(x, return_std=True)
        std = float(std[0]) if isinstance(std, np.ndarray) else float(std)
        reward = float(mean[0]) if isinstance(mean, np.ndarray) else float(mean)
        success_prob = float(np.clip(1.0 - std, 0.0, 1.0))
        return reward, std, success_prob


class BeliefStateTracker:
    """Particle filter para mantener creencias en entornos parcialmente observables."""

    def __init__(self, num_particles: int = 100) -> None:
        self.num_particles = num_particles

    def initialize(self, request: Dict[str, Any]) -> BeliefState:
        import hashlib

        seed_text = str(request.get("request_id", "")) or "42"
        seed = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16) % 2**32
        rng = np.random.default_rng(seed)
        particles = []
        for _ in range(self.num_particles):
            particles.append(
                HiddenState(
                    true_availability={},
                    true_delays={},
                    weather_condition=rng.choice(["sunny", "cloudy", "rainy", "stormy"]),
                    market_pressure=float(rng.normal(0, 0.1)),
                ).to_dict()
            )
        weights = [1.0 / self.num_particles] * self.num_particles
        return BeliefState(particles=particles, weights=weights)

    def update(
        self,
        belief: BeliefState,
        observation: Observation,
        rng: Optional[np.random.Generator] = None,
    ) -> BeliefState:
        rng = rng or np.random.default_rng()
        new_weights = []
        for p in belief.particles:
            particle = HiddenState(**p)
            likelihood = self._observation_likelihood(particle, observation)
            new_weights.append(max(1e-12, likelihood))
        total = sum(new_weights)
        new_weights = [w / total for w in new_weights]

        # Resampling sistemático
        indices = self._systematic_resample(new_weights, rng)
        new_particles = [belief.particles[i] for i in indices]
        return BeliefState(
            particles=new_particles,
            weights=[1.0 / self.num_particles] * self.num_particles,
        )

    def _observation_likelihood(self, particle: HiddenState, obs: Observation) -> float:
        import math

        # Modelo simple: el precio observado depende de market_pressure y weather
        base = 1.0
        if obs.weather in ("rainy", "stormy"):
            base *= 0.95
        expected_price = base * (1 + particle.market_pressure)
        diff = abs(obs.observed_price - expected_price * 100)
        sigma = 50.0
        return math.exp(-(diff ** 2) / (2 * sigma ** 2))

    def _systematic_resample(
        self, weights: List[float], rng: np.random.Generator
    ) -> List[int]:
        n = len(weights)
        positions = (np.arange(n) + rng.random()) / n
        cumulative = np.cumsum(weights)
        indices = []
        i = 0
        for pos in positions:
            while i < n and cumulative[i] < pos:
                i += 1
            indices.append(min(i, n - 1))
        return indices
