"""
Codificando.AI - UC-127
Integración con el SIEM (ej. Splunk HEC) para correlacionar incidentes de
LLM con otras señales de seguridad de red (ver panel "Correlación SIEM"
del dashboard de resiliencia en `UC-127.md`).
"""

from config import CONFIG
from incident_types import ActionResult, ActionStatus, IncidentRecord
from integrations.base import BaseIntegrationClient
from playbooks.loader import PlaybookStep


class SiemClient(BaseIntegrationClient):
    def send_event(self, incident: IncidentRecord, step: PlaybookStep) -> ActionResult:
        alert = incident.alert
        severity = step.params.get("severity", alert.severity.value if alert else "MEDIUM")
        payload = {
            "event": "llm_security_incident",
            "severity": severity,
            "incident_id": incident.incident_id,
            "incident_type": alert.incident_type.value if alert else None,
            "model": alert.model if alert else None,
            "summary": alert.summary if alert else None,
            "correlation_id": alert.correlation_id if alert else None,
            "source": "UC-127-Incident-Response-Orchestrator",
        }
        headers = {"Authorization": f"Splunk {CONFIG.integrations.siem_hec_token}"} \
            if CONFIG.integrations.siem_hec_token else {}
        ok = self._post(CONFIG.integrations.siem_hec_url, payload, headers=headers)
        return ActionResult(
            name=step.name,
            status=ActionStatus.SUCCESS if ok else ActionStatus.FAILED,
            detail=f"Evento de severidad {severity} enviado al SIEM" if ok else "Fallo al enviar evento al SIEM",
            requires_approval=False,
            reversible=False,
        )
