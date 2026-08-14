# UC-119 — Consultas PromQL

Consultas de Prometheus que alimentan los 8 dashboards mínimos recomendados
en `UC-119.md`. Todas las métricas son expuestas por `app.py` en `/metrics`
(ver `prometheus_metrics.py`).

## 1. Tasa de alucinaciones y fundamentación

```promql
# Tasa de alucinaciones promedio por modelo
avg(llm_hallucination_rate) by (model)

# Fundamentación (groundedness) promedio
avg(llm_groundedness_score) by (model)

# % de solicitudes con alta probabilidad de alucinación (>0.7) en 5m
sum(rate(llm_requests_total{status="high"}[5m])) by (model)
  /
sum(rate(llm_requests_total[5m])) by (model)
```

## 2. Relevancia y finalización de tareas

```promql
# Relevancia promedio
avg(llm_relevance_score) by (model)

# Fidelidad (RAG) promedio
avg(llm_fidelity_score) by (model)

# Coherencia promedio
avg(llm_coherence_score) by (model)

# Tasa de finalización de tareas
sum(rate(llm_task_completion_total{status="completed"}[5m])) by (model)
  /
sum(rate(llm_task_completion_total[5m])) by (model)

# Precisión de recuperación (RAG)
avg(llm_retrieval_precision_score) by (model)

# Satisfacción del usuario
avg(llm_user_satisfaction_score) by (model)
```

## 3. Intentos de prompt injection / jailbreak

```promql
# Intentos de evasión por minuto, por tipo
sum(rate(llm_evasion_attempts_total[1m])) by (model, type)

# Total acumulado de intentos de evasión en 1h
sum(increase(llm_evasion_attempts_total[1h])) by (model, type)

# Intentos de extracción del prompt de sistema
sum(rate(llm_prompt_extraction_attempts_total[5m])) by (model)
```

## 4. Filtración de PII y contenido tóxico

```promql
# Toxicidad en tiempo real
llm_toxicity_score{model="llama-3-8b"}

# Tasa de filtración de PII por tipo
sum(rate(llm_pii_leak_total[5m])) by (model, pii_type)

# Tasa de incumplimiento de políticas
sum(rate(llm_policy_violation_total[5m])) by (model)

# Activaciones de guardarraíles
sum(rate(llm_guardrail_activation_total[5m])) by (model, guardrail)

# Sesgo promedio detectado
avg(llm_bias_score) by (model, category)

# Eventos de acceso no autorizado
sum(rate(llm_unauthorized_access_total[5m])) by (model, tool)
```

## 5. Tokens y coste por solicitud

```promql
# Tokens de entrada/salida promedio por solicitud
histogram_quantile(0.5, sum(rate(llm_input_tokens_bucket[5m])) by (le, model))
histogram_quantile(0.5, sum(rate(llm_output_tokens_bucket[5m])) by (le, model))

# Tokens totales por usuario/función/modelo
sum(rate(llm_tokens_total[5m])) by (model, user, function)

# Coste por solicitud (mediana y P95)
histogram_quantile(0.5, sum(rate(llm_cost_per_request_usd_bucket[5m])) by (le, model))
histogram_quantile(0.95, sum(rate(llm_cost_per_request_usd_bucket[5m])) by (le, model))

# Coste total acumulado por usuario/función
sum(increase(llm_cost_total_usd[1h])) by (model, user, function)

# Tokens desperdiciados
sum(rate(llm_wasted_tokens_total[5m])) by (model)

# Tasa de aciertos de caché
sum(rate(llm_cache_hits_total[5m])) by (model)
  /
(sum(rate(llm_cache_hits_total[5m])) by (model) + sum(rate(llm_cache_misses_total[5m])) by (model))
```

## 6. TTFT y latencia P95

```promql
# TTFT P50 / P95 / P99
histogram_quantile(0.50, sum(rate(llm_ttft_seconds_bucket[5m])) by (le, model))
histogram_quantile(0.95, sum(rate(llm_ttft_seconds_bucket[5m])) by (le, model))
histogram_quantile(0.99, sum(rate(llm_ttft_seconds_bucket[5m])) by (le, model))

# Latencia total de inferencia P50 / P95 / P99
histogram_quantile(0.50, sum(rate(llm_inference_latency_seconds_bucket{phase="total"}[5m])) by (le, model))
histogram_quantile(0.95, sum(rate(llm_inference_latency_seconds_bucket{phase="total"}[5m])) by (le, model))
histogram_quantile(0.99, sum(rate(llm_inference_latency_seconds_bucket{phase="total"}[5m])) by (le, model))

# Tokens generados por segundo
avg(llm_tokens_per_second) by (model)
```

## 7. Tasa de errores y tiempos de espera

```promql
# Tasa de errores por tipo
sum(rate(llm_errors_total[5m])) by (model, error_type)

# Tasa de límites de cuota alcanzados
sum(rate(llm_rate_limit_total[5m])) by (model)

# Tasa de solicitudes bloqueadas por seguridad
sum(rate(llm_blocked_requests_total[5m])) by (model, reason)

# Tasa de error global (errores / solicitudes totales)
sum(rate(llm_errors_total[5m])) by (model)
  /
sum(rate(llm_requests_total[5m])) by (model)
```

## 8. Trazas completas (prompts, recuperaciones, llamadas a herramientas)

```promql
# Solicitudes con traza completa registrada
sum(rate(llm_traced_requests_total[5m])) by (model)

# Llamadas a herramientas por estado
sum(rate(llm_tool_calls_total[5m])) by (model, tool, status)

# Distribución de pasos de agente (P50/P95)
histogram_quantile(0.5, sum(rate(llm_agent_steps_bucket[5m])) by (le, model))
histogram_quantile(0.95, sum(rate(llm_agent_steps_bucket[5m])) by (le, model))

# Motivo de finalización de la generación
sum(rate(llm_finish_reason_total[5m])) by (model, finish_reason)
```

> Nota: para correlacionar trazas (Tempo) y logs (Loki) con estas métricas,
> use el campo `request_id` (expuesto como `correlation_id` en
> `MonitoringReport.trace` y como atributo `request_id` en spans/logs) como
> clave de correlación entre Grafana Explore (Prometheus → Loki → Tempo).
