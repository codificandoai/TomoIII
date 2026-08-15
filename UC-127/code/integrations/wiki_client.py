"""
Codificando.AI - UC-127
Integración con Wiki.js (GraphQL API) para actualizar automáticamente el
SOP (manual de procedimientos) asociado a cada tipo de incidente, dejando
una entrada versionada en Git (`commitMessage`) — la "memoria
institucional automatizada" descrita en `UC-127.md`.
"""

from config import CONFIG
from incident_types import ActionResult, ActionStatus, IncidentRecord
from integrations.base import BaseIntegrationClient
from playbooks.loader import PlaybookStep
from sop_registry import SOP_REGISTRY


class WikiClient(BaseIntegrationClient):
    def append_incident_note(self, incident: IncidentRecord, step: PlaybookStep) -> ActionResult:
        alert = incident.alert
        playbook_name = incident.playbook_name or "unknown"
        page_id = SOP_REGISTRY.get_page_id(playbook_name)

        note = (
            f"### Actualización automática post-incidente\n"
            f"- Fecha: {alert.starts_at if alert else ''}\n"
            f"- Tipo: {alert.incident_type.value if alert else ''}\n"
            f"- Severidad: {alert.severity.value if alert else ''}\n"
            f"- Resumen: {alert.summary if alert else ''}\n"
            f"- Incident ID: {incident.incident_id}\n"
        )

        payload = {
            "query": (
                "mutation($id: Int!, $content: String!, $commitMessage: String!) { "
                "pages { update(id: $id, content: $content, editor: \"markdown\", "
                "commitMessage: $commitMessage) { responseResult { succeeded } } } }"
            ),
            "variables": {
                "id": page_id,
                "content": note,
                "commitMessage": f"chore(sop): auto-append incident {incident.incident_id} ({playbook_name})",
            },
        }
        headers = {"Authorization": f"Bearer {CONFIG.integrations.wiki_api_token}"} \
            if CONFIG.integrations.wiki_api_token else {}
        ok = self._post(CONFIG.integrations.wiki_graphql_url, payload, headers=headers)

        if ok:
            SOP_REGISTRY.record_update(playbook_name, incident.incident_id)

        return ActionResult(
            name=step.name,
            status=ActionStatus.SUCCESS if ok else ActionStatus.FAILED,
            detail=f"SOP '{playbook_name}' (página {page_id}) actualizado en Wiki.js" if ok
            else f"Fallo al actualizar el SOP '{playbook_name}' en Wiki.js",
            requires_approval=False,
            reversible=False,
        )
