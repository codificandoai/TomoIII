"""
Codificando.AI
UC-129: ¿Cómo deben definirse y analizarse métricas como MTTD, MTTR, tasa
de resolución, tasa de falsos positivos, frecuencia de escalamiento,
distribución de incidentes por categoría —por ejemplo, alucinaciones,
prompt injection, jailbreak y sesgo—, latencia, carga, disponibilidad y
consumo de tokens, tanto durante como después de un incidente, para
optimizar la automatización, la asignación de recursos y la resiliencia
de las operaciones LLMOps?

Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.

Sistema de métricas de resiliencia LLMOps: rastrea el ciclo de vida
completo de cada incidente (ocurrencia -> detección -> resolución /
falso positivo / escalamiento HITL), calcula MTTD/MTTR, expone la
analítica agregada (frecuencia por tipo, tasa de resolución, tasa de
falsos positivos, frecuencia de escalamiento) y las métricas genéricas de
latencia/carga/tokens durante y después de incidentes — incluyendo la
telemetría ingerida desde Langfuse, LangSmith y LangGraph.

La lógica vive en los módulos del paquete (`config.py`,
`incident_metrics_types.py`, `classifier.py`, `incident_service.py`,
`connectors/`, `prometheus_metrics.py`). Este archivo es el punto de
entrada de línea de comandos (CLI) y sirve como demostración ejecutable
del caso de uso. Para exponer el pipeline vía API HTTP, ver `app.py`.

Uso:
    python UC-129.py                       # demo: 4 incidentes + 2 trazas ingeridas
    python UC-129.py --summary             # solo imprime la analítica agregada
"""

import argparse
import json
import sys
import time

from connectors import parse_langfuse_webhook, parse_langgraph_event, parse_langsmith_webhook
from incident_metrics_types import DetectionSource, IncidentType, ResolutionType, Severity
from incident_service import IncidentMetricsService
from logging_utils import configure_logging


def run_demo() -> int:
    configure_logging()
    service = IncidentMetricsService()

    print(f"\n{'=' * 80}\n1) Incidente de JAILBREAK detectado y resuelto automáticamente\n{'=' * 80}")
    record = service.report_event(
        incident_type=IncidentType.JAILBREAK, severity=Severity.HIGH,
        source=DetectionSource.AUTO_GUARDRAIL, model="llama-3-8b",
        summary="Patrón de jailbreak 'ignore all instructions' detectado",
    )
    time.sleep(0.05)
    service.record_detection(record.incident_id, detection_method="auto_guardrail")
    time.sleep(0.05)
    service.record_resolution(record.incident_id, ResolutionType.AUTO_REMEDIATION, success=True,
                               tokens_during_incident=340, latency_during_incident_s=1.2)
    print(json.dumps(service.get(record.incident_id).to_dict(), indent=2, ensure_ascii=False))

    print(f"\n{'=' * 80}\n2) Incidente de BIAS escalado a revisión humana (HITL)\n{'=' * 80}")
    record = service.report_event(
        incident_type=IncidentType.BIAS, severity=Severity.MEDIUM,
        source=DetectionSource.MONITORING_ALERT, model="llama-3-8b",
        summary="Sesgo de género detectado en la respuesta",
    )
    service.record_detection(record.incident_id, detection_method="monitoring_alert")
    service.record_hitl_escalation(record.incident_id, reason="contexto regulatorio ambiguo",
                                    reviewer_role="compliance_reviewer")
    service.record_resolution(record.incident_id, ResolutionType.HITL_MANUAL, success=True)
    print(json.dumps(service.get(record.incident_id).to_dict(), indent=2, ensure_ascii=False))

    print(f"\n{'=' * 80}\n3) Alerta descartada como falso positivo\n{'=' * 80}")
    record = service.report_event(
        incident_type=IncidentType.TOXICITY, severity=Severity.LOW,
        source=DetectionSource.AUTO_GUARDRAIL, model="llama-3-8b",
        summary="Falso positivo del detector de toxicidad",
    )
    service.record_detection(record.incident_id, detection_method="auto_guardrail")
    service.record_false_positive(record.incident_id)
    print(json.dumps(service.get(record.incident_id).to_dict(), indent=2, ensure_ascii=False))

    print(f"\n{'=' * 80}\n4) Ingesta de telemetría: Langfuse (traza normal)\n{'=' * 80}")
    trace = parse_langfuse_webhook({
        "id": "trace-001", "latency": 0.8, "usage": {"input": 50, "output": 120},
        "level": "DEFAULT", "tags": [], "metadata": {"model": "llama-3-8b"},
    })
    incident = service.ingest_trace(trace)
    print(json.dumps({"trace": trace.to_dict(), "incident_created": incident is not None}, indent=2, ensure_ascii=False))

    print(f"\n{'=' * 80}\n5) Ingesta de telemetría: LangSmith (run con alucinación detectada)\n{'=' * 80}")
    trace = parse_langsmith_webhook({
        "id": "run-002", "status": "success", "latency_ms": 2100,
        "prompt_tokens": 200, "completion_tokens": 400,
        "tags": ["hallucination"], "extra": {"metadata": {"model": "gpt-4o-mini"}},
    })
    incident = service.ingest_trace(trace)
    print(json.dumps({"trace": trace.to_dict(), "incident_created": incident is not None,
                       "incident": incident.to_dict() if incident else None}, indent=2, ensure_ascii=False))

    print(f"\n{'=' * 80}\n6) Ingesta de telemetría: LangGraph (nodo con error -> TOOL_FAILURE)\n{'=' * 80}")
    trace = parse_langgraph_event({
        "graph_id": "support-agent-v2", "node": "call_search_tool", "status": "error",
        "duration_ms": 500, "tokens": {"input": 30, "output": 0}, "model": "llama-3-8b",
    })
    incident = service.ingest_trace(trace)
    print(json.dumps({"trace": trace.to_dict(), "incident_created": incident is not None,
                       "incident": incident.to_dict() if incident else None}, indent=2, ensure_ascii=False))

    print(f"\n{'=' * 80}\nAnalítica agregada (panel 'Estado General')\n{'=' * 80}")
    print(json.dumps(service.summary(), indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="UC-129: Sistema de métricas de resiliencia LLMOps (MTTD/MTTR/resolución/falsos "
                     "positivos/escalamiento) con ingesta de telemetría de Langfuse/LangSmith/LangGraph."
    )
    parser.parse_args()
    return run_demo()


if __name__ == "__main__":
    sys.exit(main())