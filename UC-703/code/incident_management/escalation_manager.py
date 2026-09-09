"""Gestión de escalamiento, guardias, incident commander y acciones de contención."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from incident_management.models_incident import CommunicationRecord, Incident, IncidentStatus, OnCallPerson


class EscalationManager:
    """
    Gestiona guardias, asigna incident commander, ejecuta acciones de contención
    y envía comunicaciones automatizadas.
    """

    CONTAINMENT_ACTIONS = {
        "disable_tool": "Disable affected tool",
        "fallback_prompt": "Switch to fallback prompt/model",
        "rate_limit": "Apply rate limiting",
        "force_hitl": "Force human-in-the-loop",
        "rollback_canary": "Rollback canary deployment",
        "block_non_critical_deploys": "Block non-critical deployments",
    }

    def __init__(self) -> None:
        self._oncall: List[OnCallPerson] = []
        self._incident_commanders: Dict[str, str] = {}
        self._communications: List[CommunicationRecord] = []

    def add_oncall(self, person: OnCallPerson) -> None:
        self._oncall.append(person)

    def get_oncall_for_team(self, team: str) -> Optional[OnCallPerson]:
        active = [p for p in self._oncall if p.team == team and p.active]
        return active[0] if active else None

    def assign_incident_commander(self, incident: Incident) -> Optional[str]:
        person = self.get_oncall_for_team(incident.assigned_team or "SRE/DevOps")
        if person:
            incident.owner = person.name
            self._incident_commanders[incident.incident_id] = person.name
            return person.name
        incident.owner = "unassigned"
        return None

    def apply_containment(self, incident: Incident, actions: List[str]) -> List[str]:
        applied: List[str] = []
        for action in actions:
            if action in self.CONTAINMENT_ACTIONS:
                incident.containment_actions.append(action)
                applied.append(action)
        if applied:
            incident.status = IncidentStatus.CONTAINED.value
        return applied

    def communicate(
        self,
        incident_id: str,
        channel: str,
        recipient_team: str,
        template_name: str,
        content: str,
    ) -> CommunicationRecord:
        record = CommunicationRecord(
            incident_id=incident_id,
            channel=channel,
            recipient_team=recipient_team,
            template_name=template_name,
            content=content,
        )
        self._communications.append(record)
        return record

    def escalate_status(self, incident: Incident, new_status: str) -> None:
        incident.status = new_status

    def get_communications(self, incident_id: str = "") -> List[CommunicationRecord]:
        if not incident_id:
            return list(self._communications)
        return [c for c in self._communications if c.incident_id == incident_id]
