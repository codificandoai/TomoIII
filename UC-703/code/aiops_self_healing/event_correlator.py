"""Correlación de alertas en grupos de incidente por recurso/categoría."""
from __future__ import annotations

from typing import Dict, List, Optional

from aiops_self_healing.models_aiops import CorrelationGroup, NormalizedAlert


class EventCorrelator:
    """
    Agrupa alertas normalizadas que comparten recurso y categoría dentro de una
    ventana temporal. Cada grupo representa un incidente candidato.
    """

    def __init__(self, window_seconds: float = 300.0) -> None:
        self.window_seconds = window_seconds
        self._groups: List[CorrelationGroup] = []

    def correlate(self, alerts: List[NormalizedAlert]) -> List[CorrelationGroup]:
        groups: Dict[str, CorrelationGroup] = {}
        for alert in sorted(alerts, key=lambda a: a.timestamp):
            key = f"{alert.category}:{alert.resource}"
            existing = groups.get(key)
            if existing and abs(alert.timestamp - existing.window_end) <= self.window_seconds:
                existing.alert_ids.append(alert.alert_id)
                existing.window_end = alert.timestamp
                if alert.metric:
                    existing.symptoms.append(f"{alert.metric}={alert.value}")
                existing.severity = self._worse(existing.severity, alert.severity)
            else:
                groups[key] = CorrelationGroup(
                    alert_ids=[alert.alert_id],
                    category=alert.category,
                    resource=alert.resource,
                    severity=alert.severity,
                    window_start=alert.timestamp,
                    window_end=alert.timestamp,
                    symptoms=[f"{alert.metric}={alert.value}"] if alert.metric else [],
                )
        self._groups = list(groups.values())
        return self._groups

    @staticmethod
    def _worse(a: str, b: str) -> str:
        order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        return a if order.get(a, 0) >= order.get(b, 0) else b

    def list_groups(self) -> List[CorrelationGroup]:
        return list(self._groups)
