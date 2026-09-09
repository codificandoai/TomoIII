"""Enrutamiento de alertas al equipo responsable según categoría."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from incident_management.models_incident import Alert, Incident


class AlertRouter:
    """
    Enruta alertas al equipo responsable según la categoría del incidente:
    SRE/DevOps, QA/ML, Seguridad, Negocio/Cumplimiento.
    """

    DEFAULT_TEAMS = {
        "availability": "SRE/DevOps",
        "latency": "SRE/DevOps",
        "cost": "SRE/DevOps",
        "quality": "QA/ML",
        "security": "Security",
        "compliance": "Business/Compliance",
    }

    def __init__(self, overrides: Optional[Dict[str, str]] = None) -> None:
        self._teams = dict(self.DEFAULT_TEAMS)
        if overrides:
            self._teams.update(overrides)

    def route(self, incident: Incident, metric: str, value: float, threshold: float) -> Alert:
        team = self._teams.get(incident.category, "SRE/DevOps")
        severity = incident.severity or "medium"
        message = (
            f"Alert for {incident.category}: {metric}={value} exceeded threshold {threshold}. "
            f"Incident {incident.incident_id} severity={severity}."
        )
        return Alert(
            incident_id=incident.incident_id,
            metric=metric,
            value=value,
            threshold=threshold,
            severity=severity,
            team=team,
            message=message,
        )

    def route_custom(
        self,
        incident_id: str,
        category: str,
        metric: str,
        value: float,
        threshold: float,
        severity: str,
    ) -> Alert:
        team = self._teams.get(category, "SRE/DevOps")
        return Alert(
            incident_id=incident_id,
            metric=metric,
            value=value,
            threshold=threshold,
            severity=severity,
            team=team,
            message=(
                f"Alert for {category}: {metric}={value} exceeded threshold {threshold}."
            ),
        )
