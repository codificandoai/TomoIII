"""Controller de Incident Management LLMOps."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from incident_management.alert_router import AlertRouter
from incident_management.classifier import IncidentClassifier
from incident_management.escalation_manager import EscalationManager
from incident_management.models_incident import (
    CommunicationRecord,
    Incident,
    OnCallPerson,
    PostMortem,
    Runbook,
    SLODefinition,
    SLIDefinition,
)
from incident_management.post_mortem import PostMortemGenerator
from incident_management.runbook_engine import RunbookEngine
from incident_management.slo_engine import SLOEngine


class IncidentManagementController:
    """
    Orquesta la gestión de incidentes de LLMOps: clasificación, SLOs,
    enrutamiento de alertas, escalamiento, runbooks, comunicaciones y
    post-mortems.
    """

    def __init__(
        self,
        classifier: Optional[IncidentClassifier] = None,
        slo_engine: Optional[SLOEngine] = None,
        router: Optional[AlertRouter] = None,
        escalation: Optional[EscalationManager] = None,
        runbooks: Optional[RunbookEngine] = None,
        post_mortem: Optional[PostMortemGenerator] = None,
    ) -> None:
        self.classifier = classifier or IncidentClassifier()
        self.slo_engine = slo_engine or SLOEngine()
        self.router = router or AlertRouter()
        self.escalation = escalation or EscalationManager()
        self.runbooks = runbooks or RunbookEngine()
        self.post_mortem = post_mortem or PostMortemGenerator()
        self._incidents: Dict[str, Incident] = {}
        self._alerts: List[Any] = []

    # ------------------------------------------------------------------
    # Incident lifecycle
    # ------------------------------------------------------------------
    def create_incident(self, data: Dict[str, Any]) -> Incident:
        inc = Incident(
            title=data.get("title", ""),
            description=data.get("description", ""),
            source=data.get("source", ""),
            category=data.get("category", ""),
            urgency=data.get("urgency", "normal"),
            affected_users=int(data.get("affected_users", 0)),
            regulatory_criticality=data.get("regulatory_criticality", "none"),
            impact=data.get("impact", {}),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )
        inc.severity = self.classifier.classify(inc)
        self._incidents[inc.incident_id] = inc
        return inc

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        return self._incidents.get(incident_id)

    def list_incidents(self) -> List[Incident]:
        return list(self._incidents.values())

    def triage(self, incident_id: str) -> Optional[Incident]:
        inc = self._incidents.get(incident_id)
        if not inc:
            return None
        inc.severity = self.classifier.classify(inc)
        runbook = self.runbooks.get_runbook(inc)
        if runbook:
            inc.runbook_id = runbook.runbook_id
        # assign to team and incident commander
        alert = self.router.route(inc, "triage", 1.0, 0.0)
        inc.assigned_team = alert.team
        self.escalation.assign_incident_commander(inc)
        inc.status = "triaged"
        self._alerts.append(alert)
        return inc

    def contain(
        self,
        incident_id: str,
        actions: List[str],
    ) -> Optional[Incident]:
        inc = self._incidents.get(incident_id)
        if not inc:
            return None
        self.escalation.apply_containment(inc, actions)
        return inc

    def resolve(self, incident_id: str) -> Optional[Incident]:
        inc = self._incidents.get(incident_id)
        if not inc:
            return None
        inc.status = "resolved"
        inc.resolved_at = time.time()
        return inc

    # ------------------------------------------------------------------
    # SLOs / error budgets
    # ------------------------------------------------------------------
    def register_sli(self, sli_id: str, name: str, metric: str, unit: str, description: str = "") -> SLIDefinition:
        return self.slo_engine.register_sli(sli_id, name, metric, unit, description)

    def define_slo(self, sli_id: str, target: float, window_seconds: float, description: str = "") -> Optional[SLODefinition]:
        return self.slo_engine.define_slo(sli_id, target, window_seconds, description)

    def record_slo_sample(self, slo_id: str, good: bool) -> None:
        self.slo_engine.record_sample(slo_id, good)

    def get_error_budget(self, slo_id: str) -> Optional[Dict[str, Any]]:
        eb = self.slo_engine.compute_error_budget(slo_id)
        return eb.to_dict() if eb else None

    # ------------------------------------------------------------------
    # Alerts and routing
    # ------------------------------------------------------------------
    def create_alert(self, incident_id: str, metric: str, value: float, threshold: float) -> Optional[Any]:
        inc = self._incidents.get(incident_id)
        if not inc:
            return None
        alert = self.router.route(inc, metric, value, threshold)
        self._alerts.append(alert)
        return alert

    def list_alerts(self) -> List[Any]:
        return list(self._alerts)

    # ------------------------------------------------------------------
    # Escalation / guardia
    # ------------------------------------------------------------------
    def add_oncall(self, name: str, team: str, phone: str = "", email: str = "", active: bool = True) -> None:
        self.escalation.add_oncall(OnCallPerson(name=name, team=team, phone=phone, email=email, active=active))

    def communicate(
        self,
        incident_id: str,
        channel: str,
        recipient_team: str,
        template_name: str,
        content: str,
    ) -> CommunicationRecord:
        return self.escalation.communicate(incident_id, channel, recipient_team, template_name, content)

    # ------------------------------------------------------------------
    # Runbooks
    # ------------------------------------------------------------------
    def execute_runbook(self, incident_id: str) -> Optional[Dict[str, Any]]:
        inc = self._incidents.get(incident_id)
        if not inc:
            return None
        return self.runbooks.execute(inc)

    def list_runbooks(self) -> List[Runbook]:
        return self.runbooks.list_runbooks()

    # ------------------------------------------------------------------
    # Post-mortem
    # ------------------------------------------------------------------
    def generate_post_mortem(
        self,
        incident_id: str,
        root_cause: str,
        failed_controls: List[str],
        action_items: List[str],
        lessons_learned: str = "",
        mitigation_time_minutes: float = 0.0,
        recovery_time_minutes: float = 0.0,
    ) -> Optional[PostMortem]:
        inc = self._incidents.get(incident_id)
        if not inc:
            return None
        return self.post_mortem.generate(
            inc,
            root_cause=root_cause,
            failed_controls=failed_controls,
            action_items=action_items,
            lessons_learned=lessons_learned,
            mitigation_time_minutes=mitigation_time_minutes,
            recovery_time_minutes=recovery_time_minutes,
        )

    def dashboard(self) -> Dict[str, Any]:
        open_incidents = [i for i in self._incidents.values() if i.status not in ("resolved", "post_mortem")]
        unack_alerts = [a for a in self._alerts if not a.acknowledged]
        return {
            "total_incidents": len(self._incidents),
            "open_incidents": len(open_incidents),
            "alerts": len(self._alerts),
            "unacknowledged_alerts": len(unack_alerts),
            "oncall_count": len(self.escalation._oncall),
            "slos": len(self.slo_engine.list_slos()),
        }
