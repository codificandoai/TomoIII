"""
Codificando.AI
UC-127: ¿Qué buenas prácticas de LLMOps y respuesta automatizada a
incidentes permiten detectar y mitigar alucinaciones, prompt injection,
filtraciones de datos, degradación de calidad, fallos en herramientas y
aumentos anómalos de latencia o coste, manteniendo supervisión humana,
trazabilidad y mecanismos de reversión?

Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.

Orquestador de respuesta automatizada a incidentes de LLMOps (equivalente
funcional a un motor tipo StackStorm): clasifica telemetría/alertas en
incidentes, ejecuta manuales de procedimiento codificados (playbooks como
código, versionados en `playbooks/*.yaml`), respeta compuertas de
aprobación humana (HITL) para acciones de alto impacto, soporta reversión
(rollback), deja un registro de auditoría completo por incidente, y valida
periódicamente el pipeline mediante simulacros de Game Day (Chaos
Engineering).

La lógica vive en los módulos del paquete (`config.py`, `incident_types.py`,
`classifier.py`, `playbooks/`, `integrations/`, `orchestrator.py`,
`chaos_engineering.py`, `sop_registry.py`). Este archivo es el punto de
entrada de línea de comandos (CLI) y sirve como demostración ejecutable
del caso de uso. Para exponer el pipeline vía API HTTP, ver `app.py`.

Uso:
    python UC-127.py                          # demo de 4 incidentes + 1 simulacro
    python UC-127.py --chaos                  # ejecuta todos los simulacros de Game Day
    python UC-127.py --incident-type DATA_LEAK --severity CRITICAL
"""

import argparse
import json
import sys

from chaos_engineering import ChaosDrillRunner
from incident_types import IncidentAlert, IncidentType, Severity
from logging_utils import configure_logging
from orchestrator import IncidentResponseOrchestrator


DEMO_ALERTS = [
    IncidentAlert(
        incident_type=IncidentType.UNSAFE_GENERATION, severity=Severity.CRITICAL,
        model="llama-3-8b", model_version="3.0.1",
        summary="guardrail_blocked_ratio=18% en los últimos 2 minutos",
        source="demo", metrics={"guardrail_blocked_ratio": 0.18},
    ),
    IncidentAlert(
        incident_type=IncidentType.DATA_LEAK, severity=Severity.CRITICAL,
        model="llama-3-8b", model_version="3.0.1",
        summary="1 evento de filtración de PII (email) detectado",
        source="demo", metrics={"pii_leak_events": 1},
    ),
    IncidentAlert(
        incident_type=IncidentType.SYSTEM_OVERLOAD, severity=Severity.HIGH,
        model="llama-3-8b", model_version="3.0.1",
        summary="error_rate=12% en los últimos 5 minutos",
        source="demo", metrics={"error_rate": 0.12},
    ),
    IncidentAlert(
        incident_type=IncidentType.HALLUCINATION, severity=Severity.LOW,
        model="llama-3-8b", model_version="3.0.1",
        summary="hallucination_rate=8%, dentro de tolerancia pero en aumento",
        source="demo", metrics={"hallucination_rate": 0.08},
    ),
]


def run_demo() -> int:
    """Ejecuta 4 incidentes de demostración (uno por severidad/estado
    representativo) y un simulacro de Game Day, mostrando los reportes."""
    configure_logging()
    orchestrator = IncidentResponseOrchestrator()

    overall_status = 0
    for alert in DEMO_ALERTS:
        print(f"\n{'=' * 80}\nIncidente: {alert.incident_type.value} ({alert.severity.value})\n{'=' * 80}")
        incident = orchestrator.handle_alert(alert)
        print(json.dumps(incident.to_dict(), indent=2, ensure_ascii=False, default=str))
        if incident.status.value == "FAILED":
            overall_status = 1

    print(f"\n{'=' * 80}\nSimulacro de Game Day: pii_leak\n{'=' * 80}")
    chaos_runner = ChaosDrillRunner(orchestrator)
    drill_result = chaos_runner.run_scenario("pii_leak")
    print(json.dumps(drill_result.to_dict(), indent=2, ensure_ascii=False, default=str))
    if not drill_result.passed:
        overall_status = 1

    return overall_status


def run_chaos_suite() -> int:
    """Ejecuta todos los simulacros de Game Day definidos y reporta el
    resultado agregado (usado para validación periódica del pipeline)."""
    configure_logging()
    orchestrator = IncidentResponseOrchestrator()
    chaos_runner = ChaosDrillRunner(orchestrator)

    results = chaos_runner.run_all()
    for result in results:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False, default=str))

    return 0 if all(r.passed for r in results) else 1


def run_single(incident_type: str, severity: str, model: str, summary: str) -> int:
    configure_logging()
    orchestrator = IncidentResponseOrchestrator()
    alert = IncidentAlert(
        incident_type=IncidentType(incident_type), severity=Severity(severity),
        model=model, summary=summary, source="cli",
    )
    incident = orchestrator.handle_alert(alert)
    print(json.dumps(incident.to_dict(), indent=2, ensure_ascii=False, default=str))
    return 1 if incident.status.value == "FAILED" else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="UC-127: Orquestador de respuesta automatizada a incidentes de LLMOps."
    )
    parser.add_argument("--incident-type", type=str, choices=[t.value for t in IncidentType],
                         help="Tipo de incidente a simular.")
    parser.add_argument("--severity", type=str, choices=[s.value for s in Severity], default="MEDIUM",
                         help="Severidad del incidente.")
    parser.add_argument("--model", type=str, default="llama-3-8b", help="Modelo LLM afectado.")
    parser.add_argument("--summary", type=str, default="Incidente reportado vía CLI", help="Resumen del incidente.")
    parser.add_argument("--chaos", action="store_true", help="Ejecuta todos los simulacros de Game Day.")
    args = parser.parse_args()

    if args.chaos:
        return run_chaos_suite()

    if args.incident_type:
        return run_single(args.incident_type, args.severity, args.model, args.summary)

    return run_demo()


if __name__ == "__main__":
    sys.exit(main())
