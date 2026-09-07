"""
UC-083 — Analizador de métricas de infraestructura para respuesta a incidentes.

Detecta picos anómalos de CPU, memoria, duración y otros recursos usando
estadísticas simples (media móvil, desviación estándar, z-score).
"""

import statistics
from typing import List, Dict, Optional, Any
from collections import defaultdict

from incident_models import MetricSnapshot


class MetricsAnalyzer:
    """
    Analiza series temporales de métricas de infraestructura y detecta
    anomalías comparando contra baseline histórico.
    """

    def __init__(self):
        self._metrics: List[MetricSnapshot] = []

    def add(self, snapshot: MetricSnapshot) -> None:
        self._metrics.append(snapshot)

    def add_series(self, metric_name: str, values: List[float], timestamps: Optional[List[float]] = None, unit: str = "", source: str = "") -> None:
        """Añade una serie de métrica."""
        now = __import__("time").time()
        for i, value in enumerate(values):
            ts = timestamps[i] if timestamps else now - (len(values) - i - 1) * 60
            self._metrics.append(MetricSnapshot(
                timestamp=ts,
                metric_name=metric_name,
                value=value,
                unit=unit,
                source=source,
            ))

    def get_series(self, metric_name: str) -> List[MetricSnapshot]:
        return sorted([m for m in self._metrics if m.metric_name == metric_name], key=lambda x: x.timestamp)

    def moving_stats(self, metric_name: str, window: int = 30) -> Dict[str, float]:
        series = self.get_series(metric_name)
        values = [m.value for m in series[-window:]]
        if not values:
            return {"mean": 0.0, "stdev": 0.0, "min": 0.0, "max": 0.0}
        return {
            "mean": statistics.mean(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
        }

    def detect_spike(self, metric_name: str, z_threshold: float = 3.0, window: int = 30) -> bool:
        """Detecta si el último valor supera el umbral de z-score."""
        series = self.get_series(metric_name)
        if len(series) < window + 1:
            return False
        baseline = [m.value for m in series[-(window + 1):-1]]
        last = series[-1].value
        mean = statistics.mean(baseline)
        stdev = statistics.stdev(baseline) if len(baseline) > 1 else 0.0
        if stdev == 0:
            return last > mean
        z = (last - mean) / stdev
        return z > z_threshold

    def detect_sustained_high(self, metric_name: str, threshold: float, min_points: int = 3) -> bool:
        """Detecta si la métrica se mantiene alta durante varios puntos."""
        series = self.get_series(metric_name)
        if len(series) < min_points:
            return False
        return all(m.value >= threshold for m in series[-min_points:])

    def detect_growth_rate(self, metric_name: str, min_ratio: float = 2.0) -> bool:
        """Detecta crecimiento anómalo entre media de ventanas."""
        series = self.get_series(metric_name)
        n = len(series)
        if n < 20:
            return False
        mid = n // 2
        first = statistics.mean([m.value for m in series[:mid]])
        second = statistics.mean([m.value for m in series[mid:]])
        if first <= 0:
            return False
        return (second / first) >= min_ratio

    def summary(self) -> Dict[str, Any]:
        by_metric = defaultdict(list)
        for m in self._metrics:
            by_metric[m.metric_name].append(m.value)
        return {
            metric: {
                "count": len(vals),
                "mean": statistics.mean(vals) if vals else 0.0,
                "max": max(vals) if vals else 0.0,
                "min": min(vals) if vals else 0.0,
            }
            for metric, vals in by_metric.items()
        }

    def diagnose_resource_pressure(self, memory_threshold: float = 90.0, cpu_threshold: float = 90.0, duration_minutes: float = 120.0) -> List[Dict[str, Any]]:
        """Diagnóstico rápido de presión de recursos."""
        findings = []
        if self.detect_sustained_high("memory_percent", memory_threshold):
            findings.append({
                "type": "memory_pressure",
                "message": f"Uso de memoria sostenido >= {memory_threshold}%",
                "last_value": self.get_series("memory_percent")[-1].value,
            })
        if self.detect_sustained_high("cpu_percent", cpu_threshold):
            findings.append({
                "type": "cpu_pressure",
                "message": f"Uso de CPU sostenido >= {cpu_threshold}%",
                "last_value": self.get_series("cpu_percent")[-1].value,
            })
        duration_series = self.get_series("duration_minutes")
        if duration_series and duration_series[-1].value > duration_minutes:
            findings.append({
                "type": "duration_exceeded",
                "message": f"Duración del job {duration_series[-1].value:.1f} min > umbral {duration_minutes} min",
                "last_value": duration_series[-1].value,
            })
        return findings

    def reset(self) -> None:
        self._metrics.clear()
