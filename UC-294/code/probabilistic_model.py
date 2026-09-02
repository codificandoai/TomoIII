"""Modelos probabilísticos de transición/recompensa para UC-292.

Incluye:
- Red neuronal (MLPRegressor) para predecir éxito y recompensa.
- Proceso Gaussiano (GaussianProcessRegressor) con incertidumbre.
- Particle filter para mantener creencias en entornos parcialmente observables.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel
from sklearn.neural_network import MLPRegressor

from config import AppConfig, ProbabilisticModelConfig, get_config
from models import BeliefState, Observation


class StateEncoder:
    """Codifica estados de trading y acciones en vectores numéricos fijos."""

    _SIDE_MAP = {"HOLD": 0, "BUY": 1, "SELL": 2}

    def __init__(self, dim: int = 16) -> None:
        self.dim = dim

    def encode_state(self, state: Dict[str, Any]) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=float)
        features = state.get("features") or {}
        if isinstance(features, dict):
            vec[0] = features.get("latest_price", 0.0) / 1_000.0
            vec[1] = features.get("sma_fast", 0.0) / 1_000.0
            vec[2] = features.get("sma_slow", 0.0) / 1_000.0
            vec[3] = features.get("rsi", 50.0) / 100.0
            vec[4] = features.get("macd", 0.0) / 100.0
            vec[5] = features.get("macd_signal", 0.0) / 100.0
            vec[6] = features.get("atr", 0.0) / 100.0
            vec[7] = features.get("bollinger_position", 0.5)
            vec[8] = features.get("obv", 0.0) / 1_000_000.0
            vec[9] = features.get("volume_trend", 0)
            vec[10] = features.get("trend_direction", 0)
            vec[11] = features.get("volatility", 0.0) * 100.0
        vec[12] = state.get("price", 0.0) / 1_000.0
        vec[13] = state.get("cash", 0.0) / 1_000_000.0
        vec[14] = state.get("position", 0.0) / 1_000.0
        return self._normalize(vec)

    def encode_action(self, action: Dict[str, Any]) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=float)
        side = self._SIDE_MAP.get((action.get("side") or "HOLD").upper(), 0)
        vec[0] = side / 2.0
        vec[1] = action.get("quantity", 0.0) / 1_000.0
        vec[2] = action.get("price", 0.0) / 1_000.0
        return self._normalize(vec)

    def encode_belief(self, belief: Optional[Dict[str, Any]]) -> np.ndarray:
        """Resume belief state en features numéricas fijas."""
        vec = np.zeros(6, dtype=float)
        if not belief:
            return vec
        particles = belief.get("particles", [])
        if not particles:
            return vec
        sentiments = [p.get("sentiment", 0.0) for p in particles]
        whales = [1.0 if p.get("whale") else 0.0 for p in particles]
        vec[0] = float(np.mean(sentiments))
        vec[1] = float(np.std(sentiments)) if len(sentiments) > 1 else 0.0
        vec[2] = float(np.mean(whales))
        vec[3] = float(np.std(whales)) if len(whales) > 1 else 0.0
        vec[4] = max(0.0, min(1.0, belief.get("confidence", 0.5)))
        return vec

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
    def _normalize(vec: np.ndarray) -> np.ndarray:
        vec = np.nan_to_num(vec, nan=0.0, posinf=1e9, neginf=-1e9)
        norm = float(np.linalg.norm(vec))
        return vec if norm == 0 else vec / norm


class NeuralTransitionModel:
    """MLP para predecir éxito y recompensa de una acción de trading."""

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
        self.model_next_return = MLPRegressor(
            hidden_layer_sizes=config.hidden_layers,
            max_iter=config.max_iter,
            random_state=44,
            early_stopping=False,
        )
        self._trained = False
        self._X: List[np.ndarray] = []
        self._y_success: List[float] = []
        self._y_reward: List[float] = []
        self._y_next_return: List[float] = []

    def add_experience(
        self,
        state: Dict[str, Any],
        action: Dict[str, Any],
        next_state: Dict[str, Any],
        reward: float,
        success: bool,
        belief: Optional[Dict[str, Any]] = None,
        next_return: Optional[float] = None,
    ) -> None:
        x = self.encoder.encode_transition(state, action, belief)
        self._X.append(x)
        self._y_success.append(1.0 if success else 0.0)
        self._y_reward.append(reward)
        if next_return is None:
            p0 = state.get("price", 0.0)
            p1 = next_state.get("price", p0)
            next_return = ((p1 - p0) / p0) if p0 > 0 else 0.0
        self._y_next_return.append(next_return)

    def fit(self) -> None:
        if len(self._X) < self.config.min_samples_to_train:
            return
        X = np.array(self._X)
        self.model_success.fit(X, np.array(self._y_success))
        self.model_reward.fit(X, np.array(self._y_reward))
        if len(np.unique(self._y_next_return)) >= 2:
            self.model_next_return.fit(X, np.array(self._y_next_return))
        self._trained = True

    def predict(
        self,
        state: Dict[str, Any],
        action: Dict[str, Any],
        belief: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, float, float]:
        if not self._trained:
            return 0.5, 0.0, 1.0
        x = self.encoder.encode_transition(state, action, belief).reshape(1, -1)
        success_prob = float(np.clip(self.model_success.predict(x)[0], 0.0, 1.0))
        reward = float(self.model_reward.predict(x)[0])
        uncertainty = max(0.1, 1.0 / (1.0 + len(self._X) / 20.0))
        return success_prob, reward, uncertainty

    def predict_next_return(
        self,
        state: Dict[str, Any],
        action: Dict[str, Any],
        belief: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, float]:
        """Devuelve (predicted_return, uncertainty)."""
        if not self._trained or len(np.unique(self._y_next_return)) < 2:
            return 0.0, 1.0
        x = self.encoder.encode_transition(state, action, belief).reshape(1, -1)
        pred = float(self.model_next_return.predict(x)[0])
        uncertainty = max(0.1, 1.0 / (1.0 + len(self._X) / 20.0))
        return pred, uncertainty


class GPTransitionModel:
    """Proceso Gaussiano para recompensa con estimación de incertidumbre."""

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
        if not self._trained:
            return 0.0, 1.0, 0.5
        x = self.encoder.encode_transition(state, action, belief).reshape(1, -1)
        mean, std = self.model.predict(x, return_std=True)
        std = float(std[0]) if isinstance(std, np.ndarray) else float(std)
        reward = float(mean[0]) if isinstance(mean, np.ndarray) else float(mean)
        success_prob = float(np.clip(1.0 - std, 0.0, 1.0))
        return reward, std, success_prob


class BeliefStateTracker:
    """Particle filter para mantener creencias sobre estado oculto del mercado."""

    def __init__(self, num_particles: int = 100) -> None:
        self.num_particles = num_particles

    def initialize(self, seed_text: str = "42") -> BeliefState:
        import hashlib

        seed = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16) % 2**32
        rng = np.random.default_rng(seed)
        particles = []
        for _ in range(self.num_particles):
            particles.append(
                {
                    "sentiment": float(rng.normal(0.0, 0.2)),
                    "whale": bool(rng.random() < 0.05),
                    "vol": float(rng.exponential(0.01)),
                }
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
            likelihood = self._observation_likelihood(p, observation)
            new_weights.append(max(1e-12, likelihood))
        total = sum(new_weights)
        new_weights = [w / total for w in new_weights]
        indices = self._systematic_resample(new_weights, rng)
        new_particles = [belief.particles[i] for i in indices]
        return BeliefState(
            particles=new_particles,
            weights=[1.0 / self.num_particles] * self.num_particles,
        )

    def _observation_likelihood(self, particle: Dict[str, Any], obs: Observation) -> float:
        import math

        expected_price = 100.0 * (1.0 + particle["sentiment"])
        if particle["whale"]:
            expected_price *= 1.05
        sigma = max(1.0, obs.observed_price * obs.noise_level) if obs.noise_level > 0 else 5.0
        diff = abs(obs.observed_price - expected_price)
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
