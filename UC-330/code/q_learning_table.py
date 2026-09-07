"""
UC-330 — Tabla Q para Exploitation–Exploration Governance.

Implementa Q-learning tabular discreto con hash de contexto, optimismo
inicial y actualización por recompensas.
"""

from typing import Dict, List, Optional, Any
import math
import json
import hashlib


class QLearningTable:
    """
    Tabla Q discreta indexada por hash de contexto.

    Útil para espacios de contexto de baja dimensionalidad o como
complemento del bandido contextual.
    """

    def __init__(
        self,
        actions: List[str],
        optimistic_value: float = 0.0,
        alpha: float = 0.1,
        gamma: float = 0.95,
        hash_precision: int = 4,
    ):
        self.actions = actions
        self.optimistic_value = optimistic_value
        self.alpha = alpha
        self.gamma = gamma
        self.hash_precision = hash_precision
        self._q: Dict[str, Dict[str, float]] = {}

    def _context_hash(self, context: List[float]) -> str:
        """Genera hash determinista de un vector de contexto."""
        rounded = [round(x, self.hash_precision) for x in context]
        payload = json.dumps(rounded, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def get(self, context: List[float], action: Optional[str] = None) -> Any:
        """Retorna valores Q para un contexto."""
        key = self._context_hash(context)
        if key not in self._q:
            self._q[key] = {a: self.optimistic_value for a in self.actions}
        if action is None:
            return dict(self._q[key])
        return self._q[key].get(action, self.optimistic_value)

    def update(
        self,
        context: List[float],
        action: str,
        reward: float,
        next_context: Optional[List[float]] = None,
    ) -> None:
        """Actualiza Q(s,a) con Q-learning."""
        key = self._context_hash(context)
        if key not in self._q:
            self._q[key] = {a: self.optimistic_value for a in self.actions}
        current = self._q[key][action]

        target = reward
        if next_context is not None:
            next_values = self.get(next_context)
            target += self.gamma * max(next_values.values())

        self._q[key][action] = current + self.alpha * (target - current)

    def best_action(self, context: List[float]) -> str:
        """Retorna la acción con mayor Q-valor para el contexto."""
        values = self.get(context)
        best = max(values, key=values.get)
        return best

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "states_visited": len(self._q),
            "actions": self.actions,
            "alpha": self.alpha,
            "gamma": self.gamma,
        }

    def reset(self) -> None:
        self._q.clear()
