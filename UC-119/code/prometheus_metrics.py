"""
Codificando.AI - UC-119
Definición centralizada de métricas de Prometheus.

IMPORTANTE (corrección de bug): en la versión original del código,
`from prometheus_client import Counter` sobrescribía a
`from collections import Counter`, provocando fallos silenciosos en
`DiversityAnalyzer` (que usa `collections.Counter` para contar tokens).
Aquí se usan alias explícitos (`PromCounter`, `PromGauge`, ...) para eliminar
por completo esa colisión de nombres.
"""

from prometheus_client import (
    CollectorRegistry,
    Counter as PromCounter,
    Gauge as PromGauge,
    Histogram as PromHistogram,
    generate_latest,
    push_to_gateway,
    CONTENT_TYPE_LATEST,
)

REGISTRY = CollectorRegistry()

# ---------------------------------------------------------------------------
# 1. Métricas de calidad
# ---------------------------------------------------------------------------
hallucination_rate_gauge = PromGauge(
    'llm_hallucination_rate', 'Tasa de alucinaciones (0-1)', ['model'], registry=REGISTRY)
groundedness_gauge = PromGauge(
    'llm_groundedness_score', 'Fundamentación respecto al contexto (0-1)', ['model'], registry=REGISTRY)
relevance_gauge = PromGauge(
    'llm_relevance_score', 'Relevancia de la respuesta respecto a la pregunta (0-1)', ['model'], registry=REGISTRY)
fidelity_gauge = PromGauge(
    'llm_fidelity_score', 'Fidelidad respuesta-fuentes en sistemas RAG (0-1)', ['model'], registry=REGISTRY)
coherence_gauge = PromGauge(
    'llm_coherence_score', 'Coherencia y claridad de la respuesta (0-1)', ['model'], registry=REGISTRY)
task_completion_counter = PromCounter(
    'llm_task_completion_total', 'Solicitudes por resultado de finalización', ['model', 'status'], registry=REGISTRY)
retrieval_precision_gauge = PromGauge(
    'llm_retrieval_precision_score', 'Precisión de los documentos recuperados (0-1)', ['model'], registry=REGISTRY)
user_satisfaction_gauge = PromGauge(
    'llm_user_satisfaction_score', 'Satisfacción del usuario (0-1 o 1-5 normalizado)', ['model'], registry=REGISTRY)

input_diversity_gauge = PromGauge(
    'llm_input_diversity_score', 'Puntuación de diversidad léxica de entrada', ['model'], registry=REGISTRY)
output_diversity_gauge = PromGauge(
    'llm_output_diversity_score', 'Puntuación de diversidad léxica de salida', ['model'], registry=REGISTRY)

# ---------------------------------------------------------------------------
# 2. Métricas de seguridad
# ---------------------------------------------------------------------------
toxicity_gauge = PromGauge(
    'llm_toxicity_score', 'Puntuación de toxicidad (0-1)', ['model', 'type'], registry=REGISTRY)
bias_gauge = PromGauge(
    'llm_bias_score', 'Puntuación de sesgo detectado', ['model', 'category'], registry=REGISTRY)
evasion_attempts_counter = PromCounter(
    'llm_evasion_attempts_total', 'Total de intentos de evasión detectados (jailbreak/injection)', ['model', 'type'], registry=REGISTRY)
pii_leak_counter = PromCounter(
    'llm_pii_leak_total', 'Detecciones de filtración de PII', ['model', 'pii_type'], registry=REGISTRY)
policy_violation_counter = PromCounter(
    'llm_policy_violation_total', 'Respuestas que violan políticas internas/legales', ['model'], registry=REGISTRY)
guardrail_activation_counter = PromCounter(
    'llm_guardrail_activation_total', 'Activaciones de guardarraíles', ['model', 'guardrail'], registry=REGISTRY)
prompt_extraction_counter = PromCounter(
    'llm_prompt_extraction_attempts_total', 'Intentos de extracción del prompt de sistema', ['model'], registry=REGISTRY)
unauthorized_access_counter = PromCounter(
    'llm_unauthorized_access_total', 'Eventos de acceso no autorizado o uso inseguro de herramientas', ['model', 'tool'], registry=REGISTRY)
blocked_requests_counter = PromCounter(
    'llm_blocked_requests_total', 'Solicitudes bloqueadas por seguridad', ['model', 'reason'], registry=REGISTRY)

# ---------------------------------------------------------------------------
# 3. Métricas de coste y rendimiento
# ---------------------------------------------------------------------------
input_tokens_histogram = PromHistogram(
    'llm_input_tokens', 'Tokens de entrada por solicitud', ['model'], registry=REGISTRY)
output_tokens_histogram = PromHistogram(
    'llm_output_tokens', 'Tokens de salida por solicitud', ['model'], registry=REGISTRY)
total_tokens_counter = PromCounter(
    'llm_tokens_total', 'Tokens totales consumidos', ['model', 'user', 'function'], registry=REGISTRY)
wasted_tokens_counter = PromCounter(
    'llm_wasted_tokens_total', 'Tokens desperdiciados (contexto truncado/no usado)', ['model'], registry=REGISTRY)

cost_per_request_histogram = PromHistogram(
    'llm_cost_per_request_usd', 'Coste por solicitud en USD', ['model'], registry=REGISTRY)
cost_total_counter = PromCounter(
    'llm_cost_total_usd', 'Coste acumulado en USD', ['model', 'user', 'function'], registry=REGISTRY)

ttft_histogram = PromHistogram(
    'llm_ttft_seconds', 'Tiempo hasta el primer token (TTFT)', ['model'],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10), registry=REGISTRY)
latency_histogram = PromHistogram(
    'llm_inference_latency_seconds', 'Latencia de inferencia en segundos', ['model', 'phase'],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30), registry=REGISTRY)
tokens_per_second_gauge = PromGauge(
    'llm_tokens_per_second', 'Tokens generados por segundo', ['model'], registry=REGISTRY)

requests_counter = PromCounter(
    'llm_requests_total', 'Total de solicitudes procesadas', ['model', 'status'], registry=REGISTRY)
error_counter = PromCounter(
    'llm_errors_total', 'Errores y timeouts', ['model', 'error_type'], registry=REGISTRY)
rate_limit_counter = PromCounter(
    'llm_rate_limit_total', 'Solicitudes que agotaron límites de cuota', ['model'], registry=REGISTRY)
cache_hits_counter = PromCounter(
    'llm_cache_hits_total', 'Aciertos de caché', ['model'], registry=REGISTRY)
cache_misses_counter = PromCounter(
    'llm_cache_misses_total', 'Fallos de caché', ['model'], registry=REGISTRY)

# ---------------------------------------------------------------------------
# 4. Métricas de trazabilidad
# ---------------------------------------------------------------------------
traced_requests_counter = PromCounter(
    'llm_traced_requests_total', 'Solicitudes con traza completa registrada', ['model'], registry=REGISTRY)
tool_calls_counter = PromCounter(
    'llm_tool_calls_total', 'Llamadas a herramientas/APIs externas', ['model', 'tool', 'status'], registry=REGISTRY)
agent_steps_histogram = PromHistogram(
    'llm_agent_steps', 'Número de pasos en cadenas de razonamiento/agentes', ['model'],
    buckets=(1, 2, 3, 5, 8, 13, 21), registry=REGISTRY)
finish_reason_counter = PromCounter(
    'llm_finish_reason_total', 'Motivo de finalización de la generación', ['model', 'finish_reason'], registry=REGISTRY)
hallucination_gauge = PromGauge(
    'llm_hallucination_score', 'Puntuación de alucinación (0-1) [legacy]', ['model'], registry=REGISTRY)


def export_latest() -> bytes:
    """Serializa todas las métricas en formato texto de Prometheus."""
    return generate_latest(REGISTRY)


def push_metrics(gateway_url: str, job_name: str) -> None:
    """Empuja las métricas actuales a un Pushgateway de Prometheus."""
    push_to_gateway(gateway_url, job=job_name, registry=REGISTRY)


__all__ = [name for name in dir() if not name.startswith('_')]
