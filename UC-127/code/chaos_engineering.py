"""
Codificando.AI - UC-127
Motor de simulacros (Game Days / Chaos Engineering) para validar
periódicamente que el pipeline de respuesta a incidentes funciona de
extremo a extremo: inyecta un incidente sintético, ejecuta el
orquestador, y verifica que cada etapa esperada (detección, clasificación,
ejecución del playbook, notificación, actualización del SOP) se completó
correctamente.

Si algún paso falla, se abre automáticamente un ticket de alta prioridad
(`TicketingClient.create_gameday_failure_ticket`) para el equipo de
MLOps, tal como describe la sección "A. Simulacros Automatizados" de
`UC-127.md`.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from incident_types import ActionStatus, IncidentAlert, IncidentRecord, IncidentType, Severity
from integrations.ticketing_client import TicketingClient
from orchestrator import IncidentResponseOrchestrator
import prometheus_metrics as pm

logger = logging.getLogger(__name__)


# Escenarios de simulacro predefinidos: cada uno inyecta un `IncidentAlert`
# sintético representativo de un ataque o fallo real.
CHAOS_SCENARIOS: Dict[str, Dict[str, object]] = {
    "jailbreak_injection": {
        "incident_type": IncidentType.PROMPT_INJECTION,
        "severity": Severity.CRITICAL,
        "summary": "[SIMULACRO] Ráfaga sintética de prompts de jailbreak",
    },
    "pii_leak": {
        "incident_type": IncidentType.DATA_LEAK,
        "severity": Severity.CRITICAL,
        "summary": "[SIMULACRO] Filtración sintética de PII en la respuesta",
    },
    "traffic_spike_10x": {
        "incident_type": IncidentType.SYSTEM_OVERLOAD,
        "severity": Severity.CRITICAL,
        "summary": "[SIMULACRO] Carga de tráfico sintética 10x superior a la normal",
    },
    "hallucination_spike": {
        "incident_type": IncidentType.HALLUCINATION,
        "severity": Severity.HIGH,
        "summary": "[SIMULACRO] Aumento sintético en la tasa de alucinaciones",
    },
    "tool_outage": {
        "incident_type": IncidentType.TOOL_FAILURE,
        "severity": Severity.HIGH,
        "summary": "[SIMULACRO] Fallo sintético de una herramienta externa",
    },
}


@dataclass
class ChaosDrillResult:
    scenario: str
    incident_id: str
    passed: bool
    validated_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    ran_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ticket_created: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {
            "scenario": self.scenario,
            "incident_id": self.incident_id,
            "passed": self.passed,
            "validated_steps": self.validated_steps,
            "failed_steps": self.failed_steps,
            "ran_at": self.ran_at,
            "ticket_created": self.ticket_created,
        }


class ChaosDrillRunner:
    """Ejecuta simulacros contra un `IncidentResponseOrchestrator` real
    (en modo `is_simulation=True`) y valida que el pipeline completo se
    ejecutó como se esperaba."""

    def __init__(self, orchestrator: IncidentResponseOrchestrator, ticketing: Optional[TicketingClient] = None):
        self.orchestrator = orchestrator
        self.ticketing = ticketing or TicketingClient()

    def run_scenario(self, scenario_name: str) -> ChaosDrillResult:
        if scenario_name not in CHAOS_SCENARIOS:
            raise ValueError(f"Escenario de chaos desconocido: {scenario_name}")

        spec = CHAOS_SCENARIOS[scenario_name]
        alert = IncidentAlert(
            incident_type=spec["incident_type"],
            severity=spec["severity"],
            model="chaos-drill-model",
            summary=spec["summary"],
            source="chaos_drill",
        )

        incident = self.orchestrator.handle_alert(alert, is_simulation=True)
        result = self._validate(scenario_name, incident)

        pm.chaos_drill_total.labels(scenario=scenario_name, status="passed" if result.passed else "failed").inc()

        if not result.passed:
            result.ticket_created = self.ticketing.create_gameday_failure_ticket(scenario_name, result.failed_steps)
            logger.warning(f"Simulacro '{scenario_name}' falló en: {result.failed_steps}")
        else:
            logger.info(f"Simulacro '{scenario_name}' completado exitosamente")

        return result

    def run_all(self) -> List[ChaosDrillResult]:
        return [self.run_scenario(name) for name in CHAOS_SCENARIOS]

    @staticmethod
    def _validate(scenario_name: str, incident: IncidentRecord) -> ChaosDrillResult:
        """Verifica que el playbook ejecutó las etapas mínimas esperadas:
        clasificación (playbook asignado), notificación de colaboración,
        y actualización del SOP en Wiki.js."""
        validated, failed = [], []

        if incident.playbook_name:
            validated.append("playbook_selected")
        else:
            failed.append("playbook_selected")

        action_names = {a.name: a.status for a in incident.actions}

        notify_steps = [n for n in action_names if n.startswith("notify_")]
        if notify_steps and any(action_names[n] == ActionStatus.SUCCESS for n in notify_steps):
            validated.append("stakeholders_notified")
        else:
            failed.append("stakeholders_notified")

        if incident.status.value == "PENDING_APPROVAL":
            # El playbook se detuvo correctamente en una compuerta HITL:
            # la actualización del SOP aún no debe haber ocurrido.
            validated.append("hitl_gate_triggered_correctly")
        elif action_names.get("update_sop") == ActionStatus.SUCCESS:
            validated.append("sop_updated")
        else:
            failed.append("sop_updated")

        if incident.status.value in ("REMEDIATED", "PENDING_APPROVAL"):
            validated.append("incident_reached_terminal_or_hitl_state")
        else:
            failed.append("incident_reached_terminal_or_hitl_state")

        return ChaosDrillResult(
            scenario=scenario_name,
            incident_id=incident.incident_id,
            passed=len(failed) == 0,
            validated_steps=validated,
            failed_steps=failed,
        )
