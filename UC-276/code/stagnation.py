"""StagnationDetector — Detección de estancamiento para UC-276.

Detecta tres patrones de estancamiento en el ciclo recursivo:
1. Plateau: mejora insuficiente durante varias iteraciones.
2. Oscilación: scores fluctuando sin progreso neto.
3. Degradación: calidad descendiendo significativamente.

Inspirado en:
- kayba-ai/recursive-improve: solo sobreviven mejoras que funcionan.
- clawinfra/rsi-loop: Verify step para detectar regresión.
"""
from __future__ import annotations

from typing import List, Tuple

from config import StagnationConfig, get_config


class StagnationDetector:
    """Detecta cuando el ciclo recursivo se estanca."""

    def __init__(self, min_improvement: float = 0.02,
                 window_size: int = 3,
                 max_plateau_iterations: int = 2,
                 degradation_threshold: float = 0.05) -> None:
        self.min_improvement = min_improvement
        self.window_size = window_size
        self.max_plateau = max_plateau_iterations
        self.degradation_threshold = degradation_threshold

    @classmethod
    def from_config(cls, config: StagnationConfig | None = None) -> "StagnationDetector":
        cfg = config or get_config().stagnation
        return cls(
            min_improvement=cfg.min_improvement,
            window_size=cfg.window_size,
            max_plateau_iterations=cfg.max_plateau_iterations,
            degradation_threshold=cfg.degradation_threshold,
        )

    def is_stagnated(self, trajectory: List[float]) -> Tuple[bool, str]:
        """
        Detecta estancamiento en la trayectoria de scores.
        Returns: (is_stagnated, reason)
        """
        if len(trajectory) < 2:
            return False, ""

        # 1. Degradación: última iteración empeoró significativamente
        if trajectory[-1] < trajectory[-2] - self.degradation_threshold:
            return True, (
                f"Degradation: score dropped from {trajectory[-2]:.3f} "
                f"to {trajectory[-1]:.3f} (delta={trajectory[-1]-trajectory[-2]:.3f})"
            )

        # 2. Plateau: varias iteraciones sin mejora significativa
        plateau_count = 0
        for i in range(1, len(trajectory)):
            if trajectory[i] - trajectory[i - 1] < self.min_improvement:
                plateau_count += 1

        if plateau_count >= self.max_plateau:
            return True, (
                f"Plateau: {plateau_count} iterations with improvement "
                f"< {self.min_improvement}"
            )

        # 3. Oscilación: scores fluctuando sin progreso
        if len(trajectory) >= self.window_size:
            recent = trajectory[-self.window_size:]
            deltas = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
            signs = [1 if d > 0 else -1 for d in deltas]
            if len(set(signs)) > 1 and (max(recent) - min(recent)) < 0.05:
                return True, (
                    f"Oscillation: scores fluctuating in range "
                    f"[{min(recent):.3f}, {max(recent):.3f}] without progress"
                )

        return False, ""

    def should_rollback(self, current_score: float,
                        previous_score: float) -> bool:
        """Determina si se debe hacer rollback a la versión anterior."""
        delta = current_score - previous_score
        return delta < -self.degradation_threshold
