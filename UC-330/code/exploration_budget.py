"""
UC-330 — Presupuesto de exploración para Exploitation–Exploration Governance.

Controla cuánto presupuesto queda para exploración y ajusta la tasa de
exploración acorde a dominio y ventana temporal.
"""

from typing import Dict, Optional, Any
import time


class ExplorationBudget:
    """
    Gestiona un presupuesto de exploración por dominio y ventana temporal.

    Permite acumular, gastar y resetear presupuesto; si se agota, fuerza
modo explotación pura.
    """

    def __init__(
        self,
        total_budget: Optional[float] = None,
        window_seconds: Optional[float] = None,
    ):
        self.total_budget = total_budget
        self.window_seconds = window_seconds
        self._spent: float = 0.0
        self._domain_spent: Dict[str, float] = {}
        self._start_time: float = time.time()

    def reset_window(self) -> None:
        """Reinicia el presupuesto si la ventana temporal expiró."""
        if self.window_seconds is None:
            return
        now = time.time()
        if now - self._start_time >= self.window_seconds:
            self._spent = 0.0
            self._domain_spent.clear()
            self._start_time = now

    def remaining(self) -> Optional[float]:
        """Presupuesto restante global."""
        if self.total_budget is None:
            return None
        return max(0.0, self.total_budget - self._spent)

    def domain_remaining(self, domain: str) -> Optional[float]:
        """Presupuesto restante por dominio (distribución uniforme)."""
        if self.total_budget is None:
            return None
        # Simple per-domain cap: total / 10 by default, unless configured
        return max(0.0, self.total_budget * 0.1 - self._domain_spent.get(domain, 0.0))

    def consume(self, cost: float, domain: str = "default") -> None:
        """Registra gasto de presupuesto."""
        self._spent += cost
        self._domain_spent[domain] = self._domain_spent.get(domain, 0.0) + cost

    def allowed_epsilon(self, epsilon: float, steps_remaining: Optional[int] = None) -> float:
        """Reduce epsilon si el presupuesto es bajo."""
        remaining = self.remaining()
        if remaining is None:
            return epsilon
        if remaining <= 0:
            return 0.0
        if steps_remaining is None or steps_remaining <= 0:
            return epsilon
        # Spread remaining budget over steps
        return min(epsilon, remaining / steps_remaining)

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_budget": self.total_budget,
            "spent": self._spent,
            "remaining": self.remaining(),
            "window_seconds": self.window_seconds,
            "domain_spent": dict(self._domain_spent),
            "elapsed": round(time.time() - self._start_time, 2),
        }

    def reset(self) -> None:
        self._spent = 0.0
        self._domain_spent.clear()
        self._start_time = time.time()
