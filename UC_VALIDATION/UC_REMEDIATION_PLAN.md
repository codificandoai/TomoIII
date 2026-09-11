# UC_REMEDIATION_PLAN.md

## Plan de correcciones priorizadas

| Prioridad | Acción | UCs afectadas | Owner sugerido | Prueba de regresión |
|---|---|---|---|---|
| P0 | Asegurar que toda ejecución requiera capability_token validado | UC-300, UC-317, UC-703 | arquitectura seguridad | test de ejecución sin token rechazada |
| P1 | Implementar suite cross-UC de flujo vertical | UC-290→300→317→309→703 | integración | test end-to-end con trace_id |
| P1 | Añadir tests de leakage temporal | UC-279, UC-701, UC-702, UC-292 | ciencia de datos | test walk-forward falla si usa features futuras |
| P2 | Formalizar INPUT_CARDS en endpoints sin contrato | todas con api_*.py | API owner | test de contrato pasa |
| P2 | Unificar exportación de métricas a Prometheus/Loki/Tempo | UC-309, UC-703, UC-075 | observability | dashboard muestra métricas |
| P3 | Consolidar requirements.lock por UC | todas con .venv | DevOps | CI reproduce entorno |
