"""
Codificando.AI - UC-127
Configuración centralizada del sistema de respuesta automatizada a
incidentes de LLMOps (orquestación de playbooks, integraciones de
telemetría/SIEM/colaboración, umbrales de detección y políticas HITL).

Todos los umbrales y endpoints son configurables vía variables de entorno
para no requerir cambios de código entre entornos (dev/staging/prod).
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
    """Umbrales que determinan cuándo la telemetría constituye un incidente.

    Estos valores reflejan los disparadores (`triggers`) documentados en
    `UC-127.md` para cada playbook (ej. `guardrail_blocked > 5%`,
    `llm_latency_p99 > 5s`)."""

    hallucination_rate_warning: float = _env_float("UC127_HALLUCINATION_RATE_WARNING", 0.20)
    hallucination_rate_critical: float = _env_float("UC127_HALLUCINATION_RATE_CRITICAL", 0.40)

    guardrail_blocked_ratio_warning: float = _env_float("UC127_GUARDRAIL_BLOCKED_WARNING", 0.05)
    guardrail_blocked_ratio_critical: float = _env_float("UC127_GUARDRAIL_BLOCKED_CRITICAL", 0.15)

    evasion_attempts_per_min_warning: float = _env_float("UC127_EVASION_ATTEMPTS_WARNING", 5)
    evasion_attempts_per_min_critical: float = _env_float("UC127_EVASION_ATTEMPTS_CRITICAL", 15)

    pii_leak_events_critical: int = _env_int("UC127_PII_LEAK_EVENTS_CRITICAL", 1)

    quality_score_warning: float = _env_float("UC127_QUALITY_SCORE_WARNING", 0.6)
    quality_score_critical: float = _env_float("UC127_QUALITY_SCORE_CRITICAL", 0.4)

    tool_error_rate_warning: float = _env_float("UC127_TOOL_ERROR_RATE_WARNING", 0.10)
    tool_error_rate_critical: float = _env_float("UC127_TOOL_ERROR_RATE_CRITICAL", 0.30)

    latency_p99_warning_s: float = _env_float("UC127_LATENCY_P99_WARNING_S", 3.0)
    latency_p99_critical_s: float = _env_float("UC127_LATENCY_P99_CRITICAL_S", 5.0)

    error_rate_warning: float = _env_float("UC127_ERROR_RATE_WARNING", 0.05)
    error_rate_critical: float = _env_float("UC127_ERROR_RATE_CRITICAL", 0.10)

    cost_increase_ratio_warning: float = _env_float("UC127_COST_INCREASE_WARNING", 0.50)
    cost_increase_ratio_critical: float = _env_float("UC127_COST_INCREASE_CRITICAL", 1.0)

    incident_recurrence_7d_threshold: int = _env_int("UC127_RECURRENCE_7D_THRESHOLD", 10)
    sop_stale_days: int = _env_int("UC127_SOP_STALE_DAYS", 90)


@dataclass
class HitlConfig:
    """Política de supervisión humana (Human-In-The-Loop).

    Las acciones marcadas como `requires_approval: true` en los playbooks
    quedan en estado `PENDING_APPROVAL` hasta que un humano las apruebe o
    rechace vía la API (`/api/v1/incidents/<id>/approve`), salvo que
    `auto_approve_below_severity` lo permita para severidades bajas."""

    enabled: bool = _env_bool("UC127_HITL_ENABLED", True)
    auto_approve_below_severity: str = os.getenv("UC127_AUTO_APPROVE_BELOW_SEVERITY", "MEDIUM")
    approval_timeout_seconds: int = _env_int("UC127_APPROVAL_TIMEOUT_SECONDS", 900)


@dataclass
class IntegrationsConfig:
    """Endpoints/credenciales de las integraciones externas.

    Todas las integraciones operan en modo `dry_run` (solo registran la
    acción, sin llamada HTTP real) a menos que se configure explícitamente
    lo contrario y se provean credenciales — evita que las pruebas o un
    entorno de desarrollo intenten alcanzar servicios reales."""

    dry_run: bool = _env_bool("UC127_INTEGRATIONS_DRY_RUN", True)

    siem_hec_url: str = os.getenv("UC127_SIEM_HEC_URL", "")
    siem_hec_token: str = os.getenv("UC127_SIEM_HEC_TOKEN", "")

    slack_webhook_url: str = os.getenv("UC127_SLACK_WEBHOOK_URL", "")
    slack_security_channel: str = os.getenv("UC127_SLACK_SECURITY_CHANNEL", "#mlops-security")
    slack_infra_channel: str = os.getenv("UC127_SLACK_INFRA_CHANNEL", "#infra-oncall")

    wiki_graphql_url: str = os.getenv("UC127_WIKI_GRAPHQL_URL", "")
    wiki_api_token: str = os.getenv("UC127_WIKI_API_TOKEN", "")

    model_router_url: str = os.getenv("UC127_MODEL_ROUTER_URL", "")
    gateway_admin_url: str = os.getenv("UC127_GATEWAY_ADMIN_URL", "")  # Envoy/API Gateway admin API
    k8s_hpa_webhook_url: str = os.getenv("UC127_K8S_HPA_WEBHOOK_URL", "")

    jira_url: str = os.getenv("UC127_JIRA_URL", "")
    jira_project_key: str = os.getenv("UC127_JIRA_PROJECT_KEY", "MLOPS")
    jira_api_token: str = os.getenv("UC127_JIRA_API_TOKEN", "")

    request_timeout_s: float = _env_float("UC127_INTEGRATIONS_TIMEOUT_S", 5.0)


@dataclass
class ChaosConfig:
    """Configuración de los simulacros (Game Days / Chaos Engineering)."""

    enabled: bool = _env_bool("UC127_CHAOS_ENABLED", True)
    schedule_cron: str = os.getenv("UC127_CHAOS_SCHEDULE_CRON", "0 6 * * 1")  # semanal, lunes 06:00
    traffic_multiplier: float = _env_float("UC127_CHAOS_TRAFFIC_MULTIPLIER", 10.0)
    environment: str = os.getenv("UC127_CHAOS_ENVIRONMENT", "staging")


@dataclass
class PrometheusConfig:
    metrics_port: int = _env_int("UC127_PROMETHEUS_METRICS_PORT", 9465)


@dataclass
class TracingConfig:
    enabled: bool = _env_bool("TRACING_ENABLED", False)
    otlp_endpoint: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    service_name: str = os.getenv("OTEL_SERVICE_NAME", "uc-127-incident-response")


@dataclass
class LoggingConfig:
    level: str = os.getenv("LOG_LEVEL", "INFO")
    json_format: bool = _env_bool("LOG_JSON_FORMAT", True)


@dataclass
class AppConfig:
    thresholds: DetectionThresholds = field(default_factory=DetectionThresholds)
    hitl: HitlConfig = field(default_factory=HitlConfig)
    integrations: IntegrationsConfig = field(default_factory=IntegrationsConfig)
    chaos: ChaosConfig = field(default_factory=ChaosConfig)
    prometheus: PrometheusConfig = field(default_factory=PrometheusConfig)
    tracing: TracingConfig = field(default_factory=TracingConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


# Mapeo de nombres de alerta (Alertmanager/Grafana `alertname`) a tipos de
# incidente de UC-127. Permite que Prometheus/Grafana envíen webhooks
# estándar de Alertmanager y que el clasificador los traduzca directamente,
# sin acoplar el pipeline a nombres de alerta específicos de UC-119.
ALERT_NAME_TO_INCIDENT_TYPE: Dict[str, str] = {
    "HighHallucinationRate": "HALLUCINATION",
    "EvasionAttemptsSpike": "PROMPT_INJECTION",
    "PromptExtractionAttempt": "PROMPT_INJECTION",
    "PIILeakDetected": "DATA_LEAK",
    "UnauthorizedAccessAttempt": "DATA_LEAK",
    "LowGroundedness": "QUALITY_DEGRADATION",
    "LowTaskCompletionRate": "QUALITY_DEGRADATION",
    "HighToxicityDetected": "UNSAFE_GENERATION",
    "HighLatencyP95": "LATENCY_ANOMALY",
    "HighTTFT": "LATENCY_ANOMALY",
    "HighErrorRate": "SYSTEM_OVERLOAD",
    "LowTokensPerSecond": "SYSTEM_OVERLOAD",
    "ToolCallFailureSpike": "TOOL_FAILURE",
    "CostAnomalyDetected": "COST_ANOMALY",
}

# Causas raíz predefinidas para el cierre de incidentes (post-mortem),
# alineadas con la sección "B. Revisión Post-Mortem" de `UC-127.md`.
PREDEFINED_ROOT_CAUSES: List[str] = [
    "prompt_regression",
    "model_version_regression",
    "upstream_dependency_failure",
    "insufficient_guardrail_coverage",
    "adversarial_prompt_new_pattern",
    "traffic_spike_unplanned",
    "infrastructure_capacity_limit",
    "third_party_tool_outage",
    "context_window_overflow",
    "unknown",
]

CONFIG = AppConfig()
