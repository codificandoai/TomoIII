"""
Codificando.AI - UC-129
Registro centralizado de métricas de Prometheus para el sistema de
resiliencia LLMOps: frecuencia de incidentes por tipo, MTTD, MTTR, tasa de
resolución, falsos positivos, escalamiento HITL, y telemetría genérica
(latencia, carga/disponibilidad, tokens) durante y después de incidentes,
incluida la ingerida desde Langfuse, LangSmith y LangGraph.

Se centraliza el registro (un único `CollectorRegistry`) y se usan alias
explícitos (`PromCounter`/`PromGauge`/`PromHistogram`) para evitar la
colisión de nombres `Counter` (con `collections.Counter`) que afectó a la
versión original de `UC-129.py`.
"""

from prometheus_client import (
    CollectorRegistry,
    Counter as PromCounter,
    Gauge as PromGauge,
    Histogram as PromHistogram,
    generate_latest,
    push_to_gateway,
)

REGISTRY = CollectorRegistry()

# ---------------------------------------------------------------------------
# A. Frecuencia de incidentes por tipo (durante y después del incidente)
# ---------------------------------------------------------------------------
INCIDENTS_TOTAL = PromCounter(
    "llm_incidents_total", "Total de incidentes detectados por tipo",
    ["incident_type", "severity", "source", "phase"], registry=REGISTRY,
)

TOKENS_DURING_INCIDENT = PromCounter(
    "llm_tokens_during_incident_total", "Tokens consumidos durante incidentes activos",
    ["incident_type", "model"], registry=REGISTRY,
)

LATENCY_DURING_INCIDENT = PromHistogram(
    "llm_latency_during_incident_seconds", "Latencia de inferencia durante incidentes",
    ["incident_type"], buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0), registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# B. Efectividad de la respuesta a incidentes
# ---------------------------------------------------------------------------
MTTD_SECONDS = PromHistogram(
    "llm_incident_mttd_seconds",
    "Tiempo medio de detección (desde el evento hasta la alerta)",
    ["incident_type", "detection_method"],
    buckets=(1, 5, 10, 30, 60, 300, 600, 1800, 3600), registry=REGISTRY,
)

MTTR_SECONDS = PromHistogram(
    "llm_incident_mttr_seconds",
    "Tiempo medio de recuperación (desde la alerta hasta la resolución)",
    ["incident_type", "resolution_type"],
    buckets=(60, 300, 600, 1800, 3600, 7200, 14400, 86400), registry=REGISTRY,
)

RESOLUTIONS_TOTAL = PromCounter(
    "llm_incident_resolutions_total", "Incidentes resueltos",
    ["incident_type", "resolution_type", "success"], registry=REGISTRY,
)

FALSE_POSITIVES_TOTAL = PromCounter(
    "llm_incident_false_positives_total", "Alertas marcadas como falsos positivos",
    ["incident_type", "detection_method"], registry=REGISTRY,
)

HITL_ESCALATIONS_TOTAL = PromCounter(
    "llm_incident_hitl_escalations_total", "Incidentes escalados a revisión humana",
    ["incident_type", "escalation_reason", "reviewer_role"], registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# C. Telemetría genérica del sistema (estado, latencia, carga, tokens)
#    — alimentada por las interfaces de ingesta de Langfuse/LangSmith/LangGraph
# ---------------------------------------------------------------------------
TELEMETRY_REQUESTS_TOTAL = PromCounter(
    "llm_telemetry_requests_total", "Trazas ingeridas por fuente de observabilidad",
    ["source", "model", "status", "phase"], registry=REGISTRY,
)

TELEMETRY_LATENCY_SECONDS = PromHistogram(
    "llm_telemetry_latency_seconds", "Latencia observada en la telemetría ingerida",
    ["source", "model", "phase"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60), registry=REGISTRY,
)

TELEMETRY_TOKENS_TOTAL = PromCounter(
    "llm_telemetry_tokens_total", "Tokens observados en la telemetría ingerida",
    ["source", "model", "token_type", "phase"], registry=REGISTRY,
)

SYSTEM_LOAD_GAUGE = PromGauge(
    "llm_system_load_ratio", "Carga relativa del sistema (0-1, EWMA de la tasa de solicitudes)",
    ["source"], registry=REGISTRY,
)

SYSTEM_AVAILABILITY_GAUGE = PromGauge(
    "llm_system_availability_ratio", "Disponibilidad estimada del sistema (0-1)",
    ["source"], registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# D. Métricas de estado del propio pipeline de métricas
# ---------------------------------------------------------------------------
ACTIVE_INCIDENTS_GAUGE = PromGauge(
    "llm_active_incidents", "Incidentes actualmente sin resolver",
    ["incident_type"], registry=REGISTRY,
)


def export_latest() -> bytes:
    """Serializa el estado actual de todas las métricas en formato de
    exposición de Prometheus (usado por el endpoint `/metrics`)."""
    return generate_latest(REGISTRY)


def push_metrics(gateway_url: str, job_name: str) -> None:  # pragma: no cover - I/O externo
    push_to_gateway(gateway_url, job=job_name, registry=REGISTRY)
