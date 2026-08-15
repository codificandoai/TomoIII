"""
Codificando.AI - UC-127
Orquestador de respuesta a incidentes (equivalente funcional a un motor de
automatización tipo StackStorm): recibe un `IncidentAlert`, selecciona el
playbook codificado correspondiente, ejecuta sus pasos contra las
integraciones externas (telemetría/SIEM/colaboración), respeta las
compuertas de aprobación humana (HITL) y mantiene un registro de auditoría
completo y reversible de cada incidente.
"""

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from config import CONFIG
from incident_types import (
    ActionResult,
    ActionStatus,
    IncidentAlert,
    IncidentRecord,
    IncidentStatus,
    IncidentType,
    Severity,
)
from integrations.collaboration_client import CollaborationClient
from integrations.gateway_client import GatewayClient
from integrations.model_router_client import ModelRouterClient
from integrations.scaling_client import ScalingClient
from integrations.siem_client import SiemClient
from integrations.ticketing_client import TicketingClient
from integrations.wiki_client import WikiClient
from logging_utils import get_incident_logger
from playbooks.loader import Playbook, PlaybookLoader, PlaybookStep
import prometheus_metrics as pm
from tracing_utils import get_tracer

logger = logging.getLogger(__name__)

# Métodos de reversión (rollback) de cada acción reversible. Se invocan en
# orden inverso a la ejecución original cuando se solicita
# `rollback_incident`, implementando el mecanismo de reversión exigido por
# UC-127 sin necesidad de un motor de sagas complejo.
ROLLBACK_METHOD_MAP: Dict[str, str] = {
    "block_prompt_pattern": "remove_rule",
    "enable_rate_limiting": "disable_rate_limiting",
    "disable_tool": "enable_tool",
    "scale_out": "scale_in",
    "revert_prompt_version": "redeploy_previous_version",
    "enforce_grounding_mode": "disable_grounding_mode",
}


class IncidentResponseOrchestrator:
    """Motor central de orquestación de respuesta a incidentes de LLMOps."""

    def __init__(self, playbook_loader: Optional[PlaybookLoader] = None):
        self.playbook_loader = playbook_loader or PlaybookLoader()
        self.tracer = get_tracer()

        self.integrations = {
            "siem": SiemClient(),
            "collaboration": CollaborationClient(),
            "model_router": ModelRouterClient(),
            "gateway": GatewayClient(),
            "scaling": ScalingClient(),
            "wiki": WikiClient(),
            "ticketing": TicketingClient(),
        }

        self._lock = threading.Lock()
        self._incidents: Dict[str, IncidentRecord] = {}
        self._start_times: Dict[str, datetime] = {}

    # ------------------------------------------------------------------
    # Ciclo de vida principal del incidente
    # ------------------------------------------------------------------
    def handle_alert(self, alert: IncidentAlert, is_simulation: bool = False) -> IncidentRecord:
        """Punto de entrada principal: clasifica -> selecciona playbook ->
        ejecuta pasos -> aplica compuertas HITL -> registra auditoría."""

        incident = IncidentRecord(alert=alert, is_simulation=is_simulation)
        ilog = get_incident_logger(logger, incident.incident_id)
        ilog.info(f"Incidente detectado: {alert.incident_type.value} ({alert.severity.value})")

        with self._lock:
            self._incidents[incident.incident_id] = incident
            self._start_times[incident.incident_id] = datetime.now(timezone.utc)

        pm.incident_total.labels(incident_type=alert.incident_type.value, severity=alert.severity.value).inc()

        playbook = self.playbook_loader.get_by_incident_type(alert.incident_type)
        if playbook is None:
            incident.status = IncidentStatus.FAILED
            incident.actions.append(ActionResult(
                name="select_playbook", status=ActionStatus.FAILED,
                detail=f"No hay playbook codificado para {alert.incident_type.value}",
                requires_approval=False, reversible=False,
            ))
            self._touch(incident)
            return incident

        incident.playbook_name = playbook.name
        incident.status = IncidentStatus.RUNNING_PLAYBOOK
        incident.recurrence_count_7d = self.recurrence_last_days(alert.incident_type)

        with self.tracer.start_as_current_span("uc127_handle_incident") as span:
            span.set_attribute("incident_id", incident.incident_id)
            span.set_attribute("incident_type", alert.incident_type.value)
            span.set_attribute("playbook", playbook.name)

            self._execute_steps(incident, playbook, start_index=0)

        self._touch(incident)
        return incident

    def _execute_steps(self, incident: IncidentRecord, playbook: Playbook, start_index: int) -> None:
        ilog = get_incident_logger(logger, incident.incident_id, playbook.name)
        auto_approve_ceiling = Severity[CONFIG.hitl.auto_approve_below_severity]

        for step in playbook.steps[start_index:]:
            if step.requires_approval and CONFIG.hitl.enabled and not (
                incident.alert and incident.alert.severity < auto_approve_ceiling
            ):
                incident.actions.append(ActionResult(
                    name=step.name, status=ActionStatus.PENDING_APPROVAL,
                    detail="Acción de alto impacto en espera de aprobación humana",
                    requires_approval=True, reversible=step.reversible,
                ))
                incident.status = IncidentStatus.PENDING_APPROVAL
                pm.hitl_pending_gauge.inc()
                ilog.info(f"Paso '{step.name}' requiere aprobación humana; playbook en pausa")
                return

            self._run_step(incident, playbook, step, ilog)

        self._finalize_if_complete(incident, playbook)

    def _run_step(self, incident: IncidentRecord, playbook: Playbook, step: PlaybookStep, ilog) -> None:
        client = self.integrations.get(step.integration)
        if client is None or not hasattr(client, step.method):
            result = ActionResult(
                name=step.name, status=ActionStatus.FAILED,
                detail=f"Integración/método no encontrado: {step.integration}.{step.method}",
                requires_approval=step.requires_approval, reversible=step.reversible,
            )
        else:
            try:
                result = getattr(client, step.method)(incident, step)
            except Exception as e:  # pragma: no cover - defensivo
                ilog.exception(f"Fallo ejecutando paso '{step.name}'")
                result = ActionResult(
                    name=step.name, status=ActionStatus.FAILED, detail=str(e),
                    requires_approval=step.requires_approval, reversible=step.reversible,
                )

        incident.actions.append(result)
        pm.playbook_step_total.labels(playbook=playbook.name, step=step.name, status=result.status.value).inc()
        ilog.info(f"Paso '{step.name}' -> {result.status.value}: {result.detail}")

    def _finalize_if_complete(self, incident: IncidentRecord, playbook: Playbook) -> None:
        has_pending = any(a.status == ActionStatus.PENDING_APPROVAL for a in incident.actions)
        has_failed = any(a.status == ActionStatus.FAILED for a in incident.actions)

        if has_pending:
            incident.status = IncidentStatus.PENDING_APPROVAL
            return

        incident.status = IncidentStatus.FAILED if has_failed else IncidentStatus.REMEDIATED
        incident.resolved_at = datetime.now(timezone.utc).isoformat()

        start = self._start_times.get(incident.incident_id)
        if start:
            incident.mttr_seconds = (datetime.now(timezone.utc) - start).total_seconds()
            pm.mttr_seconds.labels(
                incident_type=incident.alert.incident_type.value if incident.alert else "unknown",
                automated="true",
            ).observe(incident.mttr_seconds)

        pm.playbook_execution_total.labels(playbook=playbook.name, status=incident.status.value).inc()

    # ------------------------------------------------------------------
    # Aprobación humana (HITL)
    # ------------------------------------------------------------------
    def approve_pending_action(self, incident_id: str, approved: bool, approver: str,
                                comment: Optional[str] = None) -> IncidentRecord:
        incident = self._require_incident(incident_id)
        ilog = get_incident_logger(logger, incident.incident_id, incident.playbook_name)

        pending = next((a for a in incident.actions if a.status == ActionStatus.PENDING_APPROVAL), None)
        if pending is None:
            raise ValueError(f"El incidente {incident_id} no tiene acciones pendientes de aprobación")

        pm.hitl_pending_gauge.dec()
        playbook = self.playbook_loader.get_by_name(incident.playbook_name)
        step_index = next(i for i, s in enumerate(playbook.steps) if s.name == pending.name)

        if not approved:
            pending.status = ActionStatus.REJECTED
            pending.detail = f"Rechazado por {approver}" + (f": {comment}" if comment else "")
            incident.status = IncidentStatus.FAILED
            incident.resolved_at = datetime.now(timezone.utc).isoformat()
            ilog.info(f"Acción '{pending.name}' rechazada por {approver}")
            self._touch(incident)
            return incident

        pending.status = ActionStatus.SUCCESS
        pending.detail = f"Aprobado por {approver}" + (f": {comment}" if comment else "")
        incident.status = IncidentStatus.RUNNING_PLAYBOOK
        ilog.info(f"Acción '{pending.name}' aprobada por {approver}; reanudando playbook")

        self._run_step(incident, playbook, playbook.steps[step_index], ilog)
        self._execute_steps(incident, playbook, start_index=step_index + 1)
        self._touch(incident)
        return incident

    # ------------------------------------------------------------------
    # Reversión (rollback)
    # ------------------------------------------------------------------
    def rollback_incident(self, incident_id: str, reason: str = "") -> IncidentRecord:
        """Revierte, en orden inverso, todas las acciones reversibles que
        se ejecutaron con éxito para este incidente."""
        incident = self._require_incident(incident_id)
        ilog = get_incident_logger(logger, incident.incident_id, incident.playbook_name)
        playbook = self.playbook_loader.get_by_name(incident.playbook_name) if incident.playbook_name else None

        reversed_any = False
        for action in reversed(incident.actions):
            if action.status != ActionStatus.SUCCESS or not action.reversible:
                continue
            step = next((s for s in (playbook.steps if playbook else []) if s.name == action.name), None)
            if step is None:
                continue
            rollback_method = ROLLBACK_METHOD_MAP.get(step.method)
            client = self.integrations.get(step.integration)
            if rollback_method and client and hasattr(client, rollback_method):
                getattr(client, rollback_method)(incident, step)
                ilog.info(f"Acción '{action.name}' revertida ({rollback_method})")
            else:
                ilog.info(f"Acción '{action.name}' marcada como revertida (sin llamada remota específica)")
            reversed_any = True

        incident.rolled_back = reversed_any
        incident.status = IncidentStatus.ROLLED_BACK
        incident.postmortem_notes = (incident.postmortem_notes or "") + f"\n[rollback] {reason}"
        if incident.playbook_name:
            pm.rollback_total.labels(playbook=incident.playbook_name).inc()
        self._touch(incident)
        return incident

    # ------------------------------------------------------------------
    # Cierre / Post-mortem
    # ------------------------------------------------------------------
    def close_incident(self, incident_id: str, root_cause: str, playbook_effective: bool,
                        postmortem_notes: Optional[str] = None) -> IncidentRecord:
        """Cierra un incidente registrando su causa raíz y si el playbook
        automatizado funcionó como se esperaba (ver sección "Revisión
        Post-Mortem" de `UC-127.md`); esta información alimenta el ciclo
        de actualización continua de SOPs."""
        incident = self._require_incident(incident_id)
        incident.root_cause = root_cause
        incident.playbook_effective = playbook_effective
        incident.postmortem_notes = postmortem_notes
        incident.status = IncidentStatus.CLOSED
        self._touch(incident)
        return incident

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def get_incident(self, incident_id: str) -> Optional[IncidentRecord]:
        return self._incidents.get(incident_id)

    def list_incidents(self, incident_type: Optional[IncidentType] = None) -> List[IncidentRecord]:
        records = list(self._incidents.values())
        if incident_type:
            records = [r for r in records if r.alert and r.alert.incident_type == incident_type]
        return sorted(records, key=lambda r: r.created_at, reverse=True)

    def recurrence_last_days(self, incident_type: IncidentType, days: int = 7) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        count = 0
        for record in self._incidents.values():
            if not record.alert or record.alert.incident_type != incident_type:
                continue
            created = datetime.fromisoformat(record.created_at)
            if created >= cutoff:
                count += 1
        pm.incident_recurrence_gauge.labels(incident_type=incident_type.value).set(count)
        return count

    # ------------------------------------------------------------------
    def _require_incident(self, incident_id: str) -> IncidentRecord:
        incident = self._incidents.get(incident_id)
        if incident is None:
            raise KeyError(f"Incidente no encontrado: {incident_id}")
        return incident

    def _touch(self, incident: IncidentRecord) -> None:
        incident.updated_at = datetime.now(timezone.utc).isoformat()
