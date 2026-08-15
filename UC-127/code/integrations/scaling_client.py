"""
Codificando.AI - UC-127
Integración con el escalador de Kubernetes (webhook que sobreescribe el
HorizontalPodAutoscaler) para escalar horizontalmente los pods de
inferencia ante una sobrecarga del sistema.
"""

from config import CONFIG
from incident_types import ActionResult, ActionStatus, IncidentRecord
from integrations.base import BaseIntegrationClient
from playbooks.loader import PlaybookStep


class ScalingClient(BaseIntegrationClient):
    def scale_out(self, incident: IncidentRecord, step: PlaybookStep) -> ActionResult:
        override_hpa = bool(step.params.get("override_hpa", False))
        payload = {
            "action": "scale_out",
            "override_hpa": override_hpa,
            "incident_id": incident.incident_id,
        }
        ok = self._post(CONFIG.integrations.k8s_hpa_webhook_url, payload)
        return ActionResult(
            name=step.name,
            status=ActionStatus.SUCCESS if ok else ActionStatus.FAILED,
            detail=(
                f"Escalado horizontal disparado (override_hpa={override_hpa})"
                if ok else "Fallo al disparar el escalado horizontal"
            ),
            requires_approval=step.requires_approval,
            reversible=True,
        )

    def scale_in(self, incident: IncidentRecord, step: PlaybookStep) -> ActionResult:
        payload = {"action": "scale_in", "incident_id": incident.incident_id}
        ok = self._post(CONFIG.integrations.k8s_hpa_webhook_url, payload)
        return ActionResult(name=f"rollback:{step.name}",
                             status=ActionStatus.SUCCESS if ok else ActionStatus.FAILED,
                             detail="Escalado horizontal revertido (scale-in)", reversible=False)
