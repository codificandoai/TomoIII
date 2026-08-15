"""
Codificando.AI - UC-127
Integración con Jira para la apertura de tickets: usada cuando un
simulacro (Game Day) falla, cuando un incidente recurrente necesita
seguimiento de ingeniería, o para el cierre de cumplimiento de una
filtración de datos.
"""

from config import CONFIG
from incident_types import ActionResult, ActionStatus, IncidentRecord
from integrations.base import BaseIntegrationClient
from playbooks.loader import PlaybookStep

# Nombres de paso que solo deben crear un ticket cuando el tipo de
# incidente es recurrente (ver `config.DetectionThresholds.incident_recurrence_7d_threshold`).
# Los tickets de cumplimiento (ej. filtración de datos) siempre se crean.
_CONDITIONAL_STEP_NAMES = {"file_ticket_if_recurrent"}


class TicketingClient(BaseIntegrationClient):
    def create_ticket(self, incident: IncidentRecord, step: PlaybookStep) -> ActionResult:
        if step.name in _CONDITIONAL_STEP_NAMES:
            threshold = CONFIG.thresholds.incident_recurrence_7d_threshold
            if incident.recurrence_count_7d < threshold:
                return ActionResult(
                    name=step.name, status=ActionStatus.SKIPPED,
                    detail=(
                        f"Sin ticket: recurrencia 7d={incident.recurrence_count_7d} "
                        f"< umbral={threshold}"
                    ),
                    requires_approval=False, reversible=False,
                )

        alert = incident.alert
        priority = step.params.get("priority", "Medium")
        payload = {
            "fields": {
                "project": {"key": CONFIG.integrations.jira_project_key},
                "summary": f"[UC-127] Incidente {alert.incident_type.value if alert else 'UNKNOWN'} - {incident.incident_id}",
                "description": alert.summary if alert else "",
                "issuetype": {"name": "Incident"},
                "priority": {"name": priority},
            }
        }
        headers = {"Authorization": f"Bearer {CONFIG.integrations.jira_api_token}"} \
            if CONFIG.integrations.jira_api_token else {}
        ok = self._post(f"{CONFIG.integrations.jira_url}/rest/api/2/issue", payload, headers=headers)
        return ActionResult(
            name=step.name,
            status=ActionStatus.SUCCESS if ok else ActionStatus.FAILED,
            detail=f"Ticket Jira ({priority}) creado para el incidente {incident.incident_id}" if ok
            else "Fallo al crear el ticket en Jira",
            requires_approval=False,
            reversible=False,
        )

    def create_gameday_failure_ticket(self, drill_name: str, failed_steps: list) -> bool:
        """Crea un ticket de alta prioridad cuando un simulacro (Game Day)
        detecta una desviación del pipeline de respuesta a incidentes."""
        payload = {
            "fields": {
                "project": {"key": CONFIG.integrations.jira_project_key},
                "summary": f"[UC-127][Game Day] Fallo en simulacro: {drill_name}",
                "description": f"Pasos fallidos: {failed_steps}",
                "issuetype": {"name": "Bug"},
                "priority": {"name": "Highest"},
            }
        }
        headers = {"Authorization": f"Bearer {CONFIG.integrations.jira_api_token}"} \
            if CONFIG.integrations.jira_api_token else {}
        return self._post(f"{CONFIG.integrations.jira_url}/rest/api/2/issue", payload, headers=headers)
