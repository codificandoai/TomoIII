"""
Codificando.AI - UC-127
Integración con el API Gateway / proxy de entrada (Envoy) para el filtrado
de patrones de prompt maliciosos, rate limiting agresivo y deshabilitación
temporal de herramientas con fallos.
"""

from config import CONFIG
from incident_types import ActionResult, ActionStatus, IncidentRecord
from integrations.base import BaseIntegrationClient
from playbooks.loader import PlaybookStep


class GatewayClient(BaseIntegrationClient):
    def block_prompt_pattern(self, incident: IncidentRecord, step: PlaybookStep) -> ActionResult:
        alert = incident.alert
        payload = {
            "action": "add_deny_rule",
            "pattern_source": "incident_correlation_id",
            "correlation_id": alert.correlation_id if alert else None,
            "incident_id": incident.incident_id,
        }
        ok = self._post(f"{CONFIG.integrations.gateway_admin_url}/rules", payload)
        return ActionResult(
            name=step.name,
            status=ActionStatus.SUCCESS if ok else ActionStatus.FAILED,
            detail="Regla de bloqueo de patrón añadida al gateway" if ok else "Fallo al añadir regla de bloqueo",
            requires_approval=step.requires_approval,
            reversible=True,
        )

    def enable_rate_limiting(self, incident: IncidentRecord, step: PlaybookStep) -> ActionResult:
        scope = step.params.get("scope", "non_critical_users")
        payload = {"action": "enable_rate_limit", "scope": scope, "incident_id": incident.incident_id}
        ok = self._post(f"{CONFIG.integrations.gateway_admin_url}/rate_limits", payload)
        return ActionResult(
            name=step.name,
            status=ActionStatus.SUCCESS if ok else ActionStatus.FAILED,
            detail=f"Rate limiting agresivo activado (scope={scope})" if ok else "Fallo al activar rate limiting",
            requires_approval=step.requires_approval,
            reversible=True,
        )

    def disable_tool(self, incident: IncidentRecord, step: PlaybookStep) -> ActionResult:
        alert = incident.alert
        tool_name = (alert.metrics.get("tool_name") if alert else None) or step.params.get("tool_name", "unknown")
        payload = {"action": "disable_tool", "tool_name": tool_name, "incident_id": incident.incident_id}
        ok = self._post(f"{CONFIG.integrations.gateway_admin_url}/tools", payload)
        return ActionResult(
            name=step.name,
            status=ActionStatus.SUCCESS if ok else ActionStatus.FAILED,
            detail=f"Herramienta '{tool_name}' deshabilitada temporalmente" if ok else "Fallo al deshabilitar herramienta",
            requires_approval=step.requires_approval,
            reversible=True,
        )

    # -- Reversión (rollback) --------------------------------------------

    def remove_rule(self, incident: IncidentRecord, step: PlaybookStep) -> ActionResult:
        ok = self._post(f"{CONFIG.integrations.gateway_admin_url}/rules/remove",
                         {"incident_id": incident.incident_id})
        return ActionResult(name=f"rollback:{step.name}",
                             status=ActionStatus.SUCCESS if ok else ActionStatus.FAILED,
                             detail="Regla de bloqueo revertida", reversible=False)

    def disable_rate_limiting(self, incident: IncidentRecord, step: PlaybookStep) -> ActionResult:
        ok = self._post(f"{CONFIG.integrations.gateway_admin_url}/rate_limits/disable",
                         {"incident_id": incident.incident_id})
        return ActionResult(name=f"rollback:{step.name}",
                             status=ActionStatus.SUCCESS if ok else ActionStatus.FAILED,
                             detail="Rate limiting agresivo desactivado", reversible=False)

    def enable_tool(self, incident: IncidentRecord, step: PlaybookStep) -> ActionResult:
        ok = self._post(f"{CONFIG.integrations.gateway_admin_url}/tools/enable",
                         {"incident_id": incident.incident_id})
        return ActionResult(name=f"rollback:{step.name}",
                             status=ActionStatus.SUCCESS if ok else ActionStatus.FAILED,
                             detail="Herramienta rehabilitada", reversible=False)
