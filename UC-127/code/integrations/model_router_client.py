"""
Codificando.AI - UC-127
Integración con el Model Router / Prompt Registry: permite revertir la
versión de prompt/modelo desplegada y forzar un modo de "fundamentación
estricta" (grounding) como contención inmediata ante alucinaciones o
generación no segura.

Estas acciones son **reversibles** (se registra la versión anterior para
poder reintentar el despliegue tras la remediación) y, por defecto,
requieren aprobación humana (`requires_approval: true` en el playbook)
dado su impacto en producción.
"""

from config import CONFIG
from incident_types import ActionResult, ActionStatus, IncidentRecord
from integrations.base import BaseIntegrationClient
from playbooks.loader import PlaybookStep


class ModelRouterClient(BaseIntegrationClient):
    def revert_prompt_version(self, incident: IncidentRecord, step: PlaybookStep) -> ActionResult:
        alert = incident.alert
        current_version = alert.model_version if alert else None
        payload = {
            "model": alert.model if alert else None,
            "current_version": current_version,
            "action": "revert_to_last_stable",
            "incident_id": incident.incident_id,
        }
        ok = self._post(CONFIG.integrations.model_router_url, payload)
        return ActionResult(
            name=step.name,
            status=ActionStatus.SUCCESS if ok else ActionStatus.FAILED,
            detail=(
                f"Prompt/modelo revertido desde la versión {current_version} a la última estable"
                if ok else "Fallo al revertir la versión de prompt/modelo"
            ),
            requires_approval=step.requires_approval,
            reversible=True,
        )

    def redeploy_previous_version(self, incident: IncidentRecord, step: PlaybookStep) -> ActionResult:
        alert = incident.alert
        payload = {
            "model": alert.model if alert else None,
            "action": "redeploy_previous_version",
            "incident_id": incident.incident_id,
        }
        ok = self._post(CONFIG.integrations.model_router_url, payload)
        return ActionResult(name=f"rollback:{step.name}",
                             status=ActionStatus.SUCCESS if ok else ActionStatus.FAILED,
                             detail="Reversión de prompt/modelo deshecha", reversible=False)

    def disable_grounding_mode(self, incident: IncidentRecord, step: PlaybookStep) -> ActionResult:
        payload = {"action": "disable_grounding_mode", "incident_id": incident.incident_id}
        ok = self._post(CONFIG.integrations.model_router_url, payload)
        return ActionResult(name=f"rollback:{step.name}",
                             status=ActionStatus.SUCCESS if ok else ActionStatus.FAILED,
                             detail="Modo de fundamentación estricta desactivado", reversible=False)

    def enforce_grounding_mode(self, incident: IncidentRecord, step: PlaybookStep) -> ActionResult:
        alert = incident.alert
        payload = {
            "model": alert.model if alert else None,
            "action": "enforce_grounding_mode",
            "incident_id": incident.incident_id,
        }
        ok = self._post(CONFIG.integrations.model_router_url, payload)
        return ActionResult(
            name=step.name,
            status=ActionStatus.SUCCESS if ok else ActionStatus.FAILED,
            detail="Modo de fundamentación estricta activado" if ok else "Fallo al activar modo de fundamentación",
            requires_approval=step.requires_approval,
            reversible=True,
        )
