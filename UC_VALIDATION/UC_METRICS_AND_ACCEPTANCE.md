# UC_METRICS_AND_ACCEPTANCE.md

## Métricas y criterios de aceptación

### Métricas financieras/predictivas
- MAE/RMSE de ASK y BID por separado.
- Error absoluto y relativo de spread.
- Directional accuracy, precision/recall/F1.
- Calibration error y cobertura de intervalos.
- Quantile loss por horizonte.
- Error condicional por régimen de volatilidad.

### Métricas operativas
- Latencia p50/p95/p99 de inferencia.
- Throughput de requests por segundo.
- Tasa de rechazo por guardrails.
- MTTD, MTTR y tasa de recurrencia.
- Cobertura de decisiones con dossier aprobado.

### Criterios de aceptación
- Ninguna ejecución sin capability token válido.
- Hash-chain de auditoría verificable.
- Test de contrato pasa >90% de endpoints.
- No leakage detectado en pruebas temporales.
- Rollback probado en sandbox.
