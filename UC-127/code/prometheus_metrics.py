"""
Codificando.AI - UC-127
Registro centralizado de métricas de Prometheus para la orquestación de
respuesta a incidentes de LLMOps. Centralizar el registro (un único
`CollectorRegistry` global de `prometheus_client`) evita doble-registro de
métricas en recargas del módulo durante los tests, y evita la colisión de
nombres `Counter` sufrida por la versión original de UC-119/UC-127 (que
importaba `Counter` de `collections` y de `prometheus_client` en el mismo
espacio de nombres).
"""

from prometheus_client import (
    CollectorRegistry,
    Counter as PromCounter,
    Gauge as PromGauge,
    Histogram as PromHistogram,
    generate_latest,
)

REGISTRY = CollectorRegistry()

incident_total = PromCounter(
    "llm_incident_total", "Incidentes de LLMOps detectados",
    ["incident_type", "severity"], registry=REGISTRY,
)

playbook_execution_total = PromCounter(
    "llm_playbook_execution_total", "Ejecuciones de playbook",
    ["playbook", "status"], registry=REGISTRY,
)

playbook_step_total = PromCounter(
    "llm_playbook_step_total", "Ejecuciones de pasos de playbook",
    ["playbook", "step", "status"], registry=REGISTRY,
)

mttr_seconds = PromHistogram(
    "llm_incident_mttr_seconds", "Tiempo medio de remediación (MTTR)",
    ["incident_type", "automated"],
    buckets=(1, 5, 15, 30, 60, 120, 300, 600, 1800, 3600),
    registry=REGISTRY,
)

hitl_pending_gauge = PromGauge(
    "llm_hitl_pending_approvals", "Acciones pendientes de aprobación humana",
    registry=REGISTRY,
)

rollback_total = PromCounter(
    "llm_incident_rollback_total", "Reversiones (rollback) de acciones de playbook",
    ["playbook"], registry=REGISTRY,
)

chaos_drill_total = PromCounter(
    "llm_chaos_drill_total", "Simulacros de Game Day ejecutados",
    ["scenario", "status"], registry=REGISTRY,
)

sop_last_updated_timestamp = PromGauge(
    "llm_sop_last_updated_timestamp", "Timestamp Unix de la última actualización del SOP",
    ["playbook"], registry=REGISTRY,
)

incident_recurrence_gauge = PromGauge(
    "llm_incident_recurrence_7d", "Recurrencia de incidentes en los últimos 7 días",
    ["incident_type"], registry=REGISTRY,
)


def export_latest() -> bytes:
    """Serializa el estado actual de todas las métricas en formato de
    exposición de Prometheus (usado por el endpoint `/metrics`)."""
    return generate_latest(REGISTRY)
