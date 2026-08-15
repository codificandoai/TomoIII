"""
Codificando.AI - UC-127
Integración con herramientas de colaboración (Slack/Teams) para alertar a
las partes interesadas durante la respuesta a un incidente.
"""

from config import CONFIG
from incident_types import ActionResult, ActionStatus, IncidentRecord
from integrations.base import BaseIntegrationClient
from playbooks.loader import PlaybookStep


class CollaborationClient(BaseIntegrationClient):
    def _notify(self, incident: IncidentRecord, step: PlaybookStep, channel: str) -> ActionResult:
        alert = incident.alert
        text = (
            f":rotating_light: *Incidente LLM: {alert.incident_type.value if alert else 'UNKNOWN'}* "
            f"({alert.severity.value if alert else 'UNKNOWN'})\n"
            f"Modelo: {alert.model if alert else 'unknown'}\n"
            f"Resumen: {alert.summary if alert else ''}\n"
            f"Incident ID: {incident.incident_id}\n"
            f"Canal: {channel}"
        )
        ok = self._post(CONFIG.integrations.slack_webhook_url, {"channel": channel, "text": text})
        return ActionResult(
            name=step.name,
            status=ActionStatus.SUCCESS if ok else ActionStatus.FAILED,
            detail=f"Notificación enviada a {channel}" if ok else f"Fallo al notificar a {channel}",
            requires_approval=False,
            reversible=False,
        )

    def notify_security(self, incident: IncidentRecord, step: PlaybookStep) -> ActionResult:
        return self._notify(incident, step, CONFIG.integrations.slack_security_channel)

    def notify_infra(self, incident: IncidentRecord, step: PlaybookStep) -> ActionResult:
        return self._notify(incident, step, CONFIG.integrations.slack_infra_channel)
