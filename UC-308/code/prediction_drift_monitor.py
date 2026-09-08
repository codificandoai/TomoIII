"""UC-308 — Monitor de deriva de predicciones para detección de concept drift.

Expone una API ligera para recopilar scores/probabilidades de predicción
y compararlas contra un baseline con Kolmogorov-Smirnov y Cramér-von Mises.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PredictionWindow:
    """Ventana deslizante de predicciones recientes."""
    agent_id: str
    tool: str
    environment: str
    agent_version: str
    scores: List[float] = field(default_factory=list)
    labels: List[Any] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)
    max_size: int = 1000

    def add(self, score: float, label: Optional[Any] = None, timestamp: Optional[float] = None) -> None:
        """Agrega una predicción."""
        self.scores.append(float(score))
        if label is not None:
            self.labels.append(label)
        self.timestamps.append(timestamp or time.time())
        if len(self.scores) > self.max_size:
            self.scores.pop(0)
            if self.labels:
                self.labels.pop(0)
            self.timestamps.pop(0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "tool": self.tool,
            "environment": self.environment,
            "agent_version": self.agent_version,
            "count": len(self.scores),
            "last_update": self.timestamps[-1] if self.timestamps else 0.0,
        }


def _ks_statistic(sample1: List[float], sample2: List[float]) -> float:
    """Estadístico D de KS two-sample."""
    if not sample1 or not sample2:
        return 0.0
    all_values = sorted(set(sample1) | set(sample2))
    diffs = []
    n1, n2 = len(sample1), len(sample2)
    for v in all_values:
        cdf1 = sum(1 for x in sample1 if x <= v) / n1
        cdf2 = sum(1 for x in sample2 if x <= v) / n2
        diffs.append(abs(cdf1 - cdf2))
    return max(diffs) if diffs else 0.0


def _cvm_statistic(sample1: List[float], sample2: List[float]) -> float:
    """Estadístico T de Cramér-von Mises two-sample."""
    if not sample1 or not sample2:
        return 0.0
    all_values = sorted(set(sample1) | set(sample2))
    t = 0.0
    n1, n2 = len(sample1), len(sample2)
    for v in all_values:
        cdf1 = sum(1 for x in sample1 if x <= v) / n1
        cdf2 = sum(1 for x in sample2 if x <= v) / n2
        t += (cdf1 - cdf2) ** 2
    return t


class PredictionDriftMonitor:
    """Recopila predicciones y detecta deriva conceptual contra un baseline."""

    def __init__(self, max_window_size: int = 1000) -> None:
        self._windows: Dict[str, PredictionWindow] = {}
        self._baselines: Dict[str, List[float]] = {}
        self.max_window_size = max_window_size

    def _window_key(self, agent_id: str, tool: str, environment: str, agent_version: str) -> str:
        return f"{agent_id}:{tool}:{environment}:{agent_version}"

    def set_baseline(
        self,
        scores: List[float],
        agent_id: str,
        tool: str,
        environment: str = "default",
        agent_version: str = "1.0.0",
    ) -> None:
        """Fija un baseline de scores para una ventana."""
        key = self._window_key(agent_id, tool, environment, agent_version)
        self._baselines[key] = [float(s) for s in scores]

    def record(
        self,
        score: float,
        agent_id: str,
        tool: str,
        environment: str = "default",
        agent_version: str = "1.0.0",
        label: Optional[Any] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """Registra un score de predicción en producción."""
        key = self._window_key(agent_id, tool, environment, agent_version)
        if key not in self._windows:
            self._windows[key] = PredictionWindow(
                agent_id=agent_id,
                tool=tool,
                environment=environment,
                agent_version=agent_version,
                max_size=self.max_window_size,
            )
        self._windows[key].add(score, label, timestamp)

    def evaluate(
        self,
        agent_id: str,
        tool: str,
        environment: str = "default",
        agent_version: str = "1.0.0",
    ) -> Dict[str, Any]:
        """Compara la ventana actual contra el baseline."""
        key = self._window_key(agent_id, tool, environment, agent_version)
        window = self._windows.get(key)
        baseline = self._baselines.get(key)

        if not window or not baseline or not window.scores:
            return {
                "drift_detected": False,
                "ks_statistic": 0.0,
                "cvm_statistic": 0.0,
                "message": "No window or baseline available",
            }

        ks = _ks_statistic(baseline, window.scores)
        cvm = _cvm_statistic(baseline, window.scores)
        base_mean = sum(baseline) / len(baseline)
        current_mean = sum(window.scores) / len(window.scores)

        return {
            "drift_detected": ks > 0.2,
            "ks_statistic": round(ks, 4),
            "cvm_statistic": round(cvm, 4),
            "base_count": len(baseline),
            "current_count": len(window.scores),
            "base_mean": round(base_mean, 4),
            "current_mean": round(current_mean, 4),
            "window": window.to_dict(),
        }

    def get_windows(self) -> Dict[str, Any]:
        """Resumen de ventanas activas."""
        return {k: w.to_dict() for k, w in self._windows.items()}
