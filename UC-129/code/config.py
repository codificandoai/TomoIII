"""
Codificando.AI - UC-129
Configuración centralizada del sistema de métricas de resiliencia LLMOps
(MTTD, MTTR, tasa de resolución, falsos positivos, escalamiento HITL,
frecuencia de incidentes por tipo, latencia/carga/tokens durante y después
de incidentes) y de las interfaces de ingesta de telemetría de Langfuse,
LangSmith y LangGraph.

Todos los umbrales son ajustables vía variables de entorno, sin modificar
código fuente (mismo patrón que `UC-119/code/config.py` y
`UC-127/code/config.py`).
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class DetectionThresholds:
    """Umbrales usados por `classifier.py` para inferir un incidente a
    partir de la telemetría ingresada desde Langfuse/LangSmith/LangGraph."""
    latency_spike_seconds: float = _env_float("UC129_LATENCY_SPIKE_SECONDS", 5.0)
    latency_critical_seconds: float = _env_float("UC129_LATENCY_CRITICAL_SECONDS", 15.0)
    system_overload_error_rate: float = _env_float("UC129_SYSTEM_OVERLOAD_ERROR_RATE", 0.10)


@dataclass
class ResilienceThresholds:
    """Umbrales de degradación de resiliencia (ver `rules/resilience.yml`
    y el panel "Estado General" del dashboard)."""
    mttd_degradation_factor: float = _env_float("UC129_MTTD_DEGRADATION_FACTOR", 2.0)
    mttr_degradation_factor: float = _env_float("UC129_MTTR_DEGRADATION_FACTOR", 1.5)
    false_positive_rate_warning: float = _env_float("UC129_FALSE_POSITIVE_RATE_WARNING", 0.30)
    hitl_escalation_rate_warning: float = _env_float("UC129_HITL_ESCALATION_RATE_WARNING", 0.50)


@dataclass
class PrometheusConfig:
    """Configuración de exportación de métricas a Prometheus."""
    pushgateway_url: str = os.getenv("PROMETHEUS_PUSHGATEWAY_URL", "localhost:9091")
    push_enabled: bool = _env_bool("PROMETHEUS_PUSH_ENABLED", False)
    job_name: str = os.getenv("PROMETHEUS_JOB_NAME", "uc129_incident_metrics")


@dataclass
class TracingConfig:
    """Configuración de trazas distribuidas (OpenTelemetry -> Tempo)."""
    enabled: bool = _env_bool("TRACING_ENABLED", False)
    otlp_endpoint: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    service_name: str = os.getenv("OTEL_SERVICE_NAME", "uc-129-incident-metrics")


@dataclass
class LoggingConfig:
    """Configuración de logging estructurado (compatible con Loki/Promtail)."""
    level: str = os.getenv("LOG_LEVEL", "INFO")
    json_format: bool = _env_bool("LOG_JSON_FORMAT", True)


@dataclass
class TelemetryIngestionConfig:
    """Configuración de las interfaces de ingesta de telemetría externa.

    Estas plataformas (Langfuse, LangSmith, LangGraph) no exponen un
    formato Prometheus nativo por trace; en su lugar, envían eventos vía
    webhook/callback que esta aplicación traduce a métricas Prometheus
    (ver `connectors/`) para que puedan ser scrapeadas por Prometheus y
    visualizadas en Grafana junto con el resto de métricas de incidentes.
    """
    langfuse_webhook_secret: str = os.getenv("LANGFUSE_WEBHOOK_SECRET", "")
    langsmith_webhook_secret: str = os.getenv("LANGSMITH_WEBHOOK_SECRET", "")
    langgraph_webhook_secret: str = os.getenv("LANGGRAPH_WEBHOOK_SECRET", "")
    auto_create_incidents: bool = _env_bool("UC129_AUTO_CREATE_INCIDENTS_FROM_TELEMETRY", True)


@dataclass
class AppConfig:
    """Configuración global de la aplicación."""
    thresholds: DetectionThresholds = field(default_factory=DetectionThresholds)
    resilience: ResilienceThresholds = field(default_factory=ResilienceThresholds)
    prometheus: PrometheusConfig = field(default_factory=PrometheusConfig)
    tracing: TracingConfig = field(default_factory=TracingConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    telemetry: TelemetryIngestionConfig = field(default_factory=TelemetryIngestionConfig)


# Categorías de incidente reconocidas a partir de tags/etiquetas presentes
# en las trazas de Langfuse/LangSmith/LangGraph (ver `classifier.py`).
INCIDENT_TAG_MAP: Dict[str, str] = {
    "hallucination": "HALLUCINATION",
    "hallucinated": "HALLUCINATION",
    "jailbreak": "JAILBREAK",
    "jailbroken": "JAILBREAK",
    "prompt_injection": "PROMPT_INJECTION",
    "injection": "PROMPT_INJECTION",
    "bias": "BIAS",
    "biased": "BIAS",
    "toxicity": "TOXICITY",
    "toxic": "TOXICITY",
    "tool_failure": "TOOL_FAILURE",
    "tool_error": "TOOL_FAILURE",
}

# Causas raíz predefinidas para el cierre de un incidente (post-mortem).
PREDEFINED_ROOT_CAUSES: List[str] = [
    "prompt_regression", "guardrail_gap", "model_drift", "data_poisoning",
    "third_party_outage", "capacity_shortage", "configuration_error",
    "false_positive_detector", "unknown",
]

CONFIG = AppConfig()
