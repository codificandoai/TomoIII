"""
Codificando.AI - UC-119
Configuración centralizada del sistema de monitoreo de LLMs.

Todos los umbrales, pesos y parámetros ajustables del pipeline se definen
aquí para evitar "números mágicos" dispersos en el código y para permitir
su modificación vía variables de entorno sin tocar el código fuente.
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
class ModelConfig:
    """Configuración del modelo LLM monitoreado."""
    model_name: str = os.getenv("LLM_MODEL_NAME", "llama-3-8b")
    provider: str = os.getenv("LLM_PROVIDER", "meta")
    model_version: str = os.getenv("LLM_MODEL_VERSION", "3.0")
    use_ml_models: bool = _env_bool("LLM_USE_ML_MODELS", False)


@dataclass
class CostConfig:
    """Precios usados para calcular coste por token (USD por 1K tokens)."""
    input_cost_per_1k: float = _env_float("LLM_INPUT_COST_PER_1K", 0.0005)
    output_cost_per_1k: float = _env_float("LLM_OUTPUT_COST_PER_1K", 0.0015)
    max_context_tokens: int = _env_int("LLM_MAX_CONTEXT_TOKENS", 8192)


@dataclass
class RiskThresholds:
    """Umbrales para clasificar niveles de riesgo (LOW/MEDIUM/HIGH/CRITICAL)."""
    toxicity_medium: float = 0.3
    toxicity_high: float = 0.6
    toxicity_critical: float = 0.8

    hallucination_medium: float = 0.4
    hallucination_high: float = 0.7

    bias_medium: float = 0.4
    bias_high: float = 0.7

    evasion_medium: float = 0.2
    evasion_high: float = 0.4
    evasion_critical: float = 0.7

    pii_leak_high: float = 0.5
    policy_violation_high: float = 0.5

    latency_p95_warning_ms: float = _env_float("LLM_LATENCY_P95_WARNING_MS", 5000)
    ttft_warning_ms: float = _env_float("LLM_TTFT_WARNING_MS", 1500)
    min_tokens_per_second: float = _env_float("LLM_MIN_TOKENS_PER_SECOND", 10)


@dataclass
class PrometheusConfig:
    """Configuración de exportación de métricas a Prometheus."""
    pushgateway_url: str = os.getenv("PROMETHEUS_PUSHGATEWAY_URL", "localhost:9091")
    push_enabled: bool = _env_bool("PROMETHEUS_PUSH_ENABLED", False)
    job_name: str = os.getenv("PROMETHEUS_JOB_NAME", "llm_monitoring")
    metrics_port: int = _env_int("PROMETHEUS_METRICS_PORT", 9464)


@dataclass
class MLflowConfig:
    """Configuración de trazabilidad y auditoría con MLflow."""
    enabled: bool = _env_bool("MLFLOW_ENABLED", False)
    tracking_uri: str = os.getenv("MLFLOW_TRACKING_URI", "file:./mlruns")
    experiment_name: str = os.getenv("MLFLOW_EXPERIMENT_NAME", "uc-119-llm-monitoring")


@dataclass
class TracingConfig:
    """Configuración de trazas distribuidas (OpenTelemetry -> Tempo)."""
    enabled: bool = _env_bool("TRACING_ENABLED", False)
    otlp_endpoint: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    service_name: str = os.getenv("OTEL_SERVICE_NAME", "uc-119-llm-monitoring")


@dataclass
class LoggingConfig:
    """Configuración de logging estructurado (compatible con Loki/Promtail)."""
    level: str = os.getenv("LOG_LEVEL", "INFO")
    json_format: bool = _env_bool("LOG_JSON_FORMAT", True)
    redact_pii: bool = _env_bool("LOG_REDACT_PII", True)


@dataclass
class AppConfig:
    """Configuración global de la aplicación."""
    model: ModelConfig = field(default_factory=ModelConfig)
    cost: CostConfig = field(default_factory=CostConfig)
    thresholds: RiskThresholds = field(default_factory=RiskThresholds)
    prometheus: PrometheusConfig = field(default_factory=PrometheusConfig)
    mlflow: MLflowConfig = field(default_factory=MLflowConfig)
    tracing: TracingConfig = field(default_factory=TracingConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


# Términos y patrones usados por los distintos analizadores. Se centralizan
# para facilitar su mantenimiento y extensión.

TOXIC_TERMS: Dict[str, List[str]] = {
    'severe': ['kill', 'murder', 'death', 'suicide', 'bomb', 'attack'],
    'obscene': ['fuck', 'shit', 'damn', 'ass'],
    'threat': ['threaten', 'harm', 'hurt', 'destroy'],
    'insult': ['stupid', 'idiot', 'dumb', 'loser', 'hate'],
    'identity_hate': ['racist', 'sexist', 'discrimination']
}

BIAS_TERMS: Dict[str, object] = {
    'gender': {
        'male': ['he', 'him', 'his', 'man', 'boy', 'male'],
        'female': ['she', 'her', 'hers', 'woman', 'girl', 'female'],
        'neutral': ['they', 'them', 'their', 'person', 'individual']
    },
    'racial': ['black', 'white', 'asian', 'latino', 'african', 'caucasian'],
    'age': ['old', 'young', 'elderly', 'teenager', 'senior', 'millennial'],
    'religious': ['christian', 'muslim', 'jewish', 'hindu', 'buddhist']
}

JAILBREAK_PATTERNS: List[str] = [
    r'ignore\s+(all\s+)?(previous\s+)?instructions',
    r'forget\s+(all\s+)?(previous\s+)?instructions',
    r'you\s+are\s+now\s+(a|an)\s+',
    r'act\s+as\s+(if\s+)?(a|an)\s+',
    r'pretend\s+(to\s+be|you\s+are)',
    r'disregard\s+(all\s+)?(previous\s+)?rules',
    r'override\s+(all\s+)?(previous\s+)?instructions',
    r'ignore\s+safety',
    r'bypass\s+(filters|restrictions|rules)',
    r'olvida\s+(las\s+)?(instrucciones|reglas)',
    r'ignora\s+(las\s+)?(instrucciones|reglas)',
    r'actúa\s+como\s+',
    r'finge\s+ser',
]

PROMPT_INJECTION_PATTERNS: List[str] = [
    r'<\|.*?\|>',
    r'\{\{.*?\}\}',
    r'\$\{.*?\}',
    r'system\s+prompt',
    r'sistema\s+prompt',
]

OBFUSCATION_PATTERNS: List[str] = [
    r'[^\w\s]{4,}',
    r'[A-Z]{6,}',
    r'\d{6,}',
]

PROMPT_EXTRACTION_PATTERNS: List[str] = [
    r'repeat\s+(your\s+)?(system\s+)?prompt',
    r'what\s+(are|is)\s+your\s+(system\s+)?instructions',
    r'show\s+me\s+your\s+(system\s+)?prompt',
    r'reveal\s+(your\s+)?(system\s+)?prompt',
    r'repite\s+tu\s+prompt',
    r'cu[aá]l\s+es\s+tu\s+prompt\s+de\s+sistema',
]

PII_PATTERNS: Dict[str, str] = {
    'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    'phone': r'\b(\+?\d{1,3}[-.\s]?)?(\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}\b',
    'credit_card': r'\b(?:\d[ -]*?){13,16}\b',
    'ssn_us': r'\b\d{3}-\d{2}-\d{4}\b',
    'ip_address': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
    'api_key': r'\b(sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16})\b',
}

POLICY_VIOLATION_TERMS: List[str] = [
    'ilegal', 'illegal', 'arma de fuego', 'firearm', 'drogas', 'narcotics',
    'explosivo', 'explosive', 'hacking', 'malware', 'ransomware'
]

UNAUTHORIZED_ACCESS_PATTERNS: List[str] = [
    r'sudo\s+', r'DROP\s+TABLE', r'rm\s+-rf', r'select\s+\*\s+from\s+users',
    r'admin\s+password', r'root\s+access', r'bypass\s+auth',
]

CONFIG = AppConfig()
