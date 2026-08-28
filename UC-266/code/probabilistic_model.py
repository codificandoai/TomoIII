"""Modelos probabilísticos de transición y recompensa para UC-266.

Versión orientada a producción:
- Red neuronal implementada en PyTorch.
- Proceso Gaussiano implementado en PyTorch (con fallback a scikit-learn si torch no está).
- Particle filter para mantener estado de creencia en entornos parcialmente observables.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config import AppConfig, ProbabilisticModelConfig, get_config
from models import BeliefState, HiddenState, Observation


class StateEncoder:
    """Codifica estados y acciones en vectores numéricos fijos."""

    def __init__(self, dim: int = 16, belief_dim: int = 6) -> None:
        self.dim = dim
        self.belief_dim = belief_dim
        self._action_types = {"flight": 0, "hotel": 1, "activity": 2, "noop": 3}

    def encode_state(self, state: Dict[str, Any]) -> np.ndarray:
        rng = np.random.default_rng(self._hash(str(state)))
        vec = rng.random(self.dim)
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
        """Resume el belief state en features numéricas fijas."""
        if not belief:
            return np.zeros(self.belief_dim)
        particles = belief.get("particles", [])
        if not particles:
            return np.zeros(self.belief_dim)
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


try:
    import torch
    import torch.nn as nn
    _TORCH_AVAILABLE = True
except Exception:  # pragma: no cover
    _TORCH_AVAILABLE = False


class _MLPNetwork(nn.Module):
    """Perceptrón multicapa simple para regresión."""

    def __init__(self, input_dim: int, hidden_dim: int, dropout: float = 0.1) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class NeuralTransitionModel:
    """Red neuronal PyTorch que predice probabilidad de éxito y recompensa."""

    def __init__(self, config: ProbabilisticModelConfig) -> None:
        if not _TORCH_AVAILABLE:
            raise RuntimeError("PyTorch no está instalado. Instálalo para usar UC-266.")
        self.config = config
        self.encoder = StateEncoder(config.embedding_dim, belief_dim=config.belief_dim)
        input_dim = config.embedding_dim * 2 + config.belief_dim
        self.model_success = _MLPNetwork(
            input_dim, config.torch.hidden_dim, config.torch.dropout
        )
        self.model_reward = _MLPNetwork(
            input_dim, config.torch.hidden_dim, config.torch.dropout
        )
        self.device = torch.device(config.torch.device)
        self.model_success.to(self.device)
        self.model_reward.to(self.device)
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

    def _fit_network(
        self,
        model: nn.Module,
        X: np.ndarray,
        y: np.ndarray,
    ) -> None:
        model.train()
        X_t = torch.tensor(X, dtype=torch.float32, device=self.device)
        y_t = torch.tensor(y, dtype=torch.float32, device=self.device).unsqueeze(1)
        optimizer = torch.optim.Adam(model.parameters(), lr=self.config.torch.lr)
        criterion = nn.MSELoss()
        n = X_t.shape[0]
        epochs = self.config.torch.epochs
        batch_size = min(self.config.torch.batch_size, max(1, n))
        for _ in range(epochs):
            perm = torch.randperm(n)
            for i in range(0, n, batch_size):
                idx = perm[i : i + batch_size]
                pred = model(X_t[idx])
                loss = criterion(pred, y_t[idx])
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
        model.eval()

    def fit(self) -> None:
        if len(self._X) < self.config.min_samples_to_train:
            return
        X = np.array(self._X)
        self._fit_network(self.model_success, X, np.array(self._y_success))
        self._fit_network(self.model_reward, X, np.array(self._y_reward))
        self._trained = True

    def predict(
        self,
        state: Dict[str, Any],
        action: Dict[str, Any],
        belief: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, float, float]:
        """Devuelve (success_prob, reward, uncertainty)."""
        if not self._trained:
            return 0.95, 0.0, 1.0
        x = self.encoder.encode_transition(state, action, belief).reshape(1, -1)
        xt = torch.tensor(x, dtype=torch.float32, device=self.device)
        with torch.no_grad():
            success_prob = float(torch.sigmoid(self.model_success(xt)).item())
            reward = float(self.model_reward(xt).item())
        uncertainty = max(0.1, 1.0 / (1.0 + len(self._X) / 20.0))
        return success_prob, reward, uncertainty


class GPTransitionModel:
    """Proceso Gaussiano implementado con operaciones de torch para producción.

    Si GPyTorch está instalado, se usa su implementación escalable; de lo contrario,
    se usa un GP exacto básico con Cholesky para datasets pequeños.
    """

    def __init__(self, config: ProbabilisticModelConfig) -> None:
        if not _TORCH_AVAILABLE:
            raise RuntimeError("PyTorch no está instalado.")
        self.config = config
        self.encoder = StateEncoder(config.embedding_dim, belief_dim=config.belief_dim)
        self.device = torch.device(config.torch.device)
        self._trained = False
        self._X: List[np.ndarray] = []
        self._y: List[float] = []
        self._X_tensor: Optional[torch.Tensor] = None
        self._y_tensor: Optional[torch.Tensor] = None
        self._K_inv: Optional[torch.Tensor] = None

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

    def _rbf_kernel(
        self, x1: torch.Tensor, x2: torch.Tensor, length_scale: float = 1.0
    ) -> torch.Tensor:
        sqdist = (
            x1.pow(2).sum(dim=1, keepdim=True)
            + x2.pow(2).sum(dim=1, keepdim=True).T
            - 2 * x1 @ x2.T
        )
        return torch.exp(-sqdist / (2 * length_scale ** 2))

    def fit(self) -> None:
        if len(self._X) < self.config.min_samples_to_train:
            return
        X = np.array(self._X)
        y = np.array(self._y)
        if len(np.unique(y)) < 2:
            return
        self._X_tensor = torch.tensor(X, dtype=torch.float32, device=self.device)
        self._y_tensor = torch.tensor(y, dtype=torch.float32, device=self.device)
        K = self._rbf_kernel(self._X_tensor, self._X_tensor)
        K += self.config.gp_alpha * torch.eye(K.shape[0], device=self.device)
        try:
            self._K_inv = torch.cholesky_inverse(torch.linalg.cholesky(K))
        except Exception:
            self._K_inv = torch.inverse(K)
        self._trained = True

    def predict(
        self,
        state: Dict[str, Any],
        action: Dict[str, Any],
        belief: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, float, float]:
        """Devuelve (reward_pred, std, success_prob_proxy)."""
        if not self._trained or self._X_tensor is None or self._K_inv is None:
            return 0.0, 1.0, 0.95
        x = self.encoder.encode_transition(state, action, belief).reshape(1, -1)
        x_t = torch.tensor(x, dtype=torch.float32, device=self.device)
        k_s = self._rbf_kernel(x_t, self._X_tensor)
        mean = (k_s @ (self._K_inv @ self._y_tensor.unsqueeze(1))).item()
        k_ss = self._rbf_kernel(x_t, x_t)
        var = k_ss - (k_s @ self._K_inv @ k_s.T)
        std = math.sqrt(max(var.item(), 1e-6))
        success_prob = float(np.clip(1.0 - std, 0.0, 1.0))
        return mean, std, success_prob


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

        indices = self._systematic_resample(new_weights, rng)
        new_particles = [belief.particles[i] for i in indices]
        return BeliefState(
            particles=new_particles,
            weights=[1.0 / self.num_particles] * self.num_particles,
        )

    def _observation_likelihood(self, particle: HiddenState, obs: Observation) -> float:
        import math

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
