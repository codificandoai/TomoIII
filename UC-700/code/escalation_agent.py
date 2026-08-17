"""UC-700 — Agente de escalamiento a operador.

Paso 10: Escalar a un operador si no se cumple el objetivo.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from config import AgentConfig
from models import Incident


class EscalationAgent:
    """Paso 10: Escalar a operador humano cuando la autosanación no cumple objetivo."""

    def __init__(self, config: AgentConfig):
        self.config = config

    def evaluate(self, incident: Incident) -> Dict[str, Any]:
        """Decide si cerrar incidente o escalar a operador."""
        reasons = []
        should_escalate = False

        if incident.escalated:
            should_escalate = True
            reasons.append("already_marked_escalated")

        if incident.severity in self.config.require_human_approval:
            should_escalate = True
            reasons.append(f"severity_{incident.severity}_requires_human_approval")

        efficiency = incident.efficiency or {}
        if not efficiency.get("acceptable", True):
            should_escalate = True
            reasons.append("efficiency_below_threshold")

        validation = incident.validation or {}
        if not validation.get("valid", True):
            should_escalate = True
            reasons.append("validation_failed")

        plan = incident.plan
        if plan and plan.requires_approval:
            should_escalate = True
            reasons.append("remediation_plan_requires_approval")

        if should_escalate:
            incident.escalated = True
            incident.state = "ESCALATED"
            self._notify_operator(incident)
            return {
                "escalated": True,
                "incident_id": incident.id,
                "severity": incident.severity,
                "reasons": reasons,
                "channel": "pagerduty-sre-oncall",
                "timestamp": datetime.utcnow().isoformat(),
                "message": self._build_message(incident),
            }

        incident.state = "CLOSED"
        incident.resolved_at = datetime.utcnow()
        return {
            "escalated": False,
            "incident_id": incident.id,
            "state": incident.state,
            "reasons": ["autosanacion_exitosa"],
            "timestamp": incident.resolved_at.isoformat(),
        }

    def _notify_operator(self, incident: Incident) -> None:
        # En producción: integrar con PagerDuty/Opsgenie/Servicenow
        pass

    def _build_message(self, incident: Incident) -> str:
        return (
            f"[ESCALACION] Incidente {incident.id} en nodo {incident.node_id} "
            f"({incident.failure_class}/{incident.severity}) requiere intervención humana. "
            f"Trace: {len(incident.trace)} pasos."
        )
