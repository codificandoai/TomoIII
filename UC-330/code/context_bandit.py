"""
UC-330 — Bandido Contextual para Exploitation–Exploration Governance.

Implementa LinUCB y Thompson Sampling sobre modelos lineales por acción.
"""

from typing import Dict, List, Optional, Any, Tuple
import math
import random

import numpy as np


class ContextualBandit:
    """
    Bandido contextual con aproximación lineal.

    Cada acción mantiene un modelo lineal con regularización Ridge, lo que
permite estimar recompensa esperada e incertidumbre para UCB y Thompson.
    """

    def __init__(
        self,
        actions: List[str],
        feature_dim: int,
        alpha: float = 1.0,
        regularization: float = 0.1,
    ):
        self.actions = actions
        self.feature_dim = feature_dim
        self.alpha = alpha
        self.reg = regularization
        self._models: Dict[str, Dict[str, np.ndarray]] = {}
        for action in actions:
            A = np.eye(feature_dim) * self.reg
            b = np.zeros((feature_dim, 1))
            self._models[action] = {"A": A, "b": b, "trials": 0}

    def update(self, context: List[float], action: str, reward: float) -> None:
        """Actualiza el modelo lineal de una acción con una observación."""
        if action not in self._models:
            return
        x = np.array(context).reshape(-1, 1)
        self._models[action]["A"] += x @ x.T
        self._models[action]["b"] += reward * x
        self._models[action]["trials"] += 1

    def predict(self, context: List[float], action: str) -> Tuple[float, float]:
        """
        Retorna (recompensa esperada, incertidumbre) para una acción.

        Incertidumbre = x^T A^{-1} x.
        """
        if action not in self._models:
            return 0.0, float("inf")
        x = np.array(context).reshape(-1, 1)
        model = self._models[action]
        A_inv = np.linalg.inv(model["A"])
        theta = A_inv @ model["b"]
        mean = float((x.T @ theta).item())
        uncertainty = float((x.T @ A_inv @ x).item())
        return mean, uncertainty

    def select_ucb(self, context: List[float], kappa: float = 1.0) -> str:
        """Selecciona acción por Upper Confidence Bound."""
        best_action = self.actions[0]
        best_score = -float("inf")
        for action in self.actions:
            mean, uncertainty = self.predict(context, action)
            score = mean + kappa * math.sqrt(max(0.0, uncertainty))
            if score > best_score:
                best_score = score
                best_action = action
        return best_action

    def select_thompson(self, context: List[float]) -> str:
        """Selecciona acción por Thompson Sampling."""
        best_action = self.actions[0]
        best_sample = -float("inf")
        x = np.array(context).reshape(-1, 1)
        for action in self.actions:
            model = self._models[action]
            A_inv = np.linalg.inv(model["A"])
            theta = A_inv @ model["b"]
            cov = A_inv
            try:
                sample_theta = np.random.multivariate_normal(
                    theta.flatten(), cov * self.alpha
                )
                sample = float((x.T @ sample_theta.reshape(-1, 1)).item())
            except Exception:
                sample = float((x.T @ theta).item())
            if sample > best_sample:
                best_sample = sample
                best_action = action
        return best_action

    def select_directed(self, context: List[float]) -> str:
        """Selecciona acción con mayor potencial de aprendizaje (alta incertidumbre)."""
        best_action = self.actions[0]
        best_uncertainty = -float("inf")
        for action in self.actions:
            _, uncertainty = self.predict(context, action)
            if uncertainty > best_uncertainty:
                best_uncertainty = uncertainty
                best_action = action
        return best_action

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "actions": self.actions,
            "feature_dim": self.feature_dim,
            "trials_by_action": {a: m["trials"] for a, m in self._models.items()},
        }

    def reset(self) -> None:
        for action in self.actions:
            A = np.eye(self.feature_dim) * self.reg
            b = np.zeros((self.feature_dim, 1))
            self._models[action] = {"A": A, "b": b, "trials": 0}
