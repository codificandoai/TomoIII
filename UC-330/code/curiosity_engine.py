"""
UC-330 — Curiosidad Intrínseca para Exploitation–Exploration Governance.

Implementa un modelo de predicción de dinámica simple (modelo lineal) que
estima el siguiente contexto dado el contexto actual y la acción. El error
de predicción se usa como bonus de exploración intrínseca.
"""

from typing import Dict, List, Any, Optional, Tuple
import math

import numpy as np


class CuriosityEngine:
    """
    Motor de curiosidad intrínseca basado en error de predicción.

    Mantiene un modelo lineal por acción: s_{t+1} ≈ W_a * s_t + b_a.
    El error MSE normalizado se convierte en bonus de recompensa.
    """

    def __init__(
        self,
        actions: List[str],
        feature_dim: int,
        learning_rate: float = 0.01,
        eta: float = 0.5,
    ):
        self.actions = actions
        self.feature_dim = feature_dim
        self.learning_rate = learning_rate
        self.eta = eta
        self._models: Dict[str, Dict[str, np.ndarray]] = {}
        self._errors: List[float] = []
        for action in actions:
            W = np.zeros((feature_dim, feature_dim))
            b = np.zeros((feature_dim, 1))
            self._models[action] = {"W": W, "b": b}

    def predict_next(
        self,
        context: List[float],
        action: str,
    ) -> np.ndarray:
        """Predice el siguiente contexto."""
        if action not in self._models:
            return np.zeros((self.feature_dim, 1))
        x = np.array(context).reshape(-1, 1)
        W = self._models[action]["W"]
        b = self._models[action]["b"]
        return W @ x + b

    def compute_bonus(
        self,
        context: List[float],
        action: str,
        next_context: List[float],
    ) -> float:
        """Calcula bonus de curiosidad = error de predicción normalizado."""
        pred = self.predict_next(context, action)
        actual = np.array(next_context).reshape(-1, 1)
        error = float(np.mean((actual - pred) ** 2))

        self._errors.append(error)
        avg_error = np.mean(self._errors[-100:]) if self._errors else 1e-9
        bonus = self.eta * error / (1.0 + avg_error)
        return bonus

    def update(
        self,
        context: List[float],
        action: str,
        next_context: List[float],
    ) -> None:
        """Actualiza el modelo de dinámica con SGD."""
        if action not in self._models:
            return
        x = np.array(context).reshape(-1, 1)
        y = np.array(next_context).reshape(-1, 1)
        pred = self.predict_next(context, action)
        grad = (pred - y) @ x.T
        self._models[action]["W"] -= self.learning_rate * grad
        self._models[action]["b"] -= self.learning_rate * (pred - y)

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "actions": self.actions,
            "feature_dim": self.feature_dim,
            "avg_error": round(float(np.mean(self._errors[-100:])), 6) if self._errors else 0.0,
            "total_updates": len(self._errors),
        }

    def reset(self) -> None:
        for action in self.actions:
            self._models[action]["W"] = np.zeros((self.feature_dim, self.feature_dim))
            self._models[action]["b"] = np.zeros((self.feature_dim, 1))
        self._errors.clear()
