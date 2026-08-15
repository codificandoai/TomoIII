# UC-127 — Consultas PromQL

Consultas que alimentan el dashboard "LLMOps Resilience & Automation
Tracker" descrito en `UC-127.md`. Todas las métricas son expuestas por
`app.py` en `/metrics` (ver `prometheus_metrics.py`).

## 1. Efectividad de la automatización (MTTR)

```promql
# MTTR promedio por tipo de incidente (remediación automatizada)
avg(rate(llm_incident_mttr_seconds_sum{automated="true"}[1h])
  / rate(llm_incident_mttr_seconds_count{automated="true"}[1h])) by (incident_type)

# MTTR P50/P95 (segundos)
histogram_quantile(0.5, sum(rate(llm_incident_mttr_seconds_bucket[1h])) by (le, incident_type))
histogram_quantile(0.95, sum(rate(llm_incident_mttr_seconds_bucket[1h])) by (le, incident_type))

# Incidentes por tipo y severidad (volumen)
sum(increase(llm_incident_total[24h])) by (incident_type, severity)

# Tasa de éxito de ejecución de playbooks
sum(rate(llm_playbook_execution_total{status="REMEDIATED"}[1h])) by (playbook)
  /
sum(rate(llm_playbook_execution_total[1h])) by (playbook)

# Acciones pendientes de aprobación humana en este momento
llm_hitl_pending_approvals

# Reversiones (rollback) ejecutadas
sum(increase(llm_incident_rollback_total[24h])) by (playbook)
```

## 2. Salud del SOP (Wiki.js)

```promql
# Tiempo (en días) desde la última actualización de cada SOP
(time() - llm_sop_last_updated_timestamp) / 86400

# SOPs sin actualizar en más de `sop_stale_days` (90 días por defecto)
(time() - llm_sop_last_updated_timestamp) / 86400 > 90
```

> El detalle completo (última actualización, último incidente asociado)
> se consulta vía la API REST (`GET /api/v1/sops`), ya que Wiki.js no
> expone esta información como serie temporal de Prometheus.

## 3. Correlación con el SIEM

```promql
# Incidentes de seguridad de LLM (candidatos a correlación SIEM)
sum(increase(llm_incident_total{incident_type=~"PROMPT_INJECTION|DATA_LEAK|UNSAFE_GENERATION"}[1h])) by (incident_type)

# Recurrencia de un tipo de incidente en los últimos 7 días
llm_incident_recurrence_7d
```

## 4. Validación de simulacros (Game Days)

```promql
# Resultado de los simulacros de Game Day por escenario
sum(increase(llm_chaos_drill_total[7d])) by (scenario, status)

# Tasa de éxito de los simulacros
sum(rate(llm_chaos_drill_total{status="passed"}[7d]))
  /
sum(rate(llm_chaos_drill_total[7d]))
```

## 5. Pasos de playbook (detalle operativo)

```promql
# Tasa de fallo por paso de playbook (para detectar integraciones inestables)
sum(rate(llm_playbook_step_total{status="FAILED"}[1h])) by (playbook, step)
  /
sum(rate(llm_playbook_step_total[1h])) by (playbook, step)
```
