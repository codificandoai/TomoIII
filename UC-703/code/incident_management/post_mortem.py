"""Generador de post-mortems sin culpas para incidentes LLMOps."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from incident_management.models_incident import Incident, PostMortem


class PostMortemGenerator:
    """
    Produce un análisis post-incidente estructurado con tiempos, controles
    fallidos, causa raíz y acciones preventivas.
    """

    def generate(
        self,
        incident: Incident,
        root_cause: str,
        failed_controls: List[str],
        action_items: List[str],
        lessons_learned: str = "",
        mitigation_time_minutes: float = 0.0,
        recovery_time_minutes: float = 0.0,
    ) -> PostMortem:
        detected = incident.detected_at
        now = incident.resolved_at or mitigation_time_minutes * 60 + detected
        detection_time_minutes = 0.0
        if detected and now:
            detection_time_minutes = max(0.0, (now - detected) / 60.0)
        pm = PostMortem(
            incident_id=incident.incident_id,
            summary=f"Post-mortem for {incident.title} ({incident.incident_id})",
            root_cause=root_cause,
            impact={
                "affected_users": incident.affected_users,
                "category": incident.category,
                "severity": incident.severity,
                "regulatory_criticality": incident.regulatory_criticality,
            },
            detection_time_minutes=round(detection_time_minutes, 2),
            mitigation_time_minutes=round(mitigation_time_minutes, 2),
            recovery_time_minutes=round(recovery_time_minutes, 2),
            failed_controls=failed_controls,
            action_items=action_items,
            lessons_learned=lessons_learned or "Document findings and update controls.",
        )
        incident.status = "post_mortem"
        return pm
