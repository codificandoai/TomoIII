"""
UC-330 — Detector de cambios del entorno para Exploitation–Exploration Governance.

Detecta cambios estructurales y tendencias en series de recompensas para
decidir si se debe reiniciar la exploración.
"""

from typing import List, Dict, Any, Optional
import statistics
import math


class EnvironmentDetector:
    """
    Detecta cambios en la distribución de recompensas usando ventanas
    deslizantes y una prueba de diferencia de medias simple.
    """

    def __init__(
        self,
        change_window: int = 100,
        change_threshold: float = 0.15,
    ):
        self.change_window = change_window
        self.change_threshold = change_threshold
        self.rewards: List[float] = []
        self.change_points: List[int] = []

    def add_reward(self, reward: float) -> None:
        """Registra una nueva recompensa."""
        self.rewards.append(reward)

    def detect_change(self) -> bool:
        """
        Detecta cambio comparando medias de dos ventanas consecutivas.

        Retorna True si la diferencia relativa supera el umbral.
        """
        n = len(self.rewards)
        if n < 2 * self.change_window:
            return False

        recent = self.rewards[-self.change_window:]
        previous = self.rewards[-2 * self.change_window:-self.change_window]

        mean_recent = statistics.mean(recent)
        mean_previous = statistics.mean(previous)

        denom = abs(mean_previous) if mean_previous != 0 else 1e-9
        relative_change = abs(mean_recent - mean_previous) / denom

        if relative_change > self.change_threshold:
            self.change_points.append(n)
            return True
        return False

    def trend_direction(self) -> str:
        """Indica si la tendencia reciente es ascendente, descendente o estable."""
        if len(self.rewards) < self.change_window:
            return "insufficient_data"
        recent = self.rewards[-self.change_window:]
        previous = self.rewards[-min(2 * self.change_window, len(self.rewards)):-self.change_window]
        if not previous:
            return "insufficient_data"
        diff = statistics.mean(recent) - statistics.mean(previous)
        if abs(diff) < self.change_threshold * max(abs(statistics.mean(previous)), 1e-9):
            return "stable"
        return "upward" if diff > 0 else "downward"

    def volatility(self) -> float:
        """Calcula la desviación estándar de las últimas recompensas."""
        if len(self.rewards) < 2:
            return 0.0
        window = self.rewards[-self.change_window:]
        return statistics.stdev(window) if len(window) > 1 else 0.0

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_rewards": len(self.rewards),
            "change_points": self.change_points,
            "last_change_point": self.change_points[-1] if self.change_points else None,
            "trend_direction": self.trend_direction(),
            "volatility": round(self.volatility(), 6),
            "change_window": self.change_window,
            "change_threshold": self.change_threshold,
        }

    def reset(self) -> None:
        self.rewards.clear()
        self.change_points.clear()
