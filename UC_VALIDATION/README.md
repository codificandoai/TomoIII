# UC_VALIDATION — Validación Integral del Ecosistema AGI

Este directorio contiene los artefactos de la validación integral entre UCs del repositorio TomoIII.

## Scripts

- `inventory.py` — descubre UCs, endpoints, tests y contratos declarados.
- `generate_reports.py` — genera los markdowns de análisis estático.
- `run_uc_tests.py` — ejecuta pytest en cada UC y recolecta resultados.
- `generate_integration_report.py` — produce `UC_INTEGRATION_TEST_REPORT.md`.

## Artefactos generados

1. `UC_INTEROPERABILITY_MAP.md`
2. `UC_API_CONTRACT_MATRIX.md`
3. `UC_DATA_LINEAGE_AND_LEAKAGE_AUDIT.md`
4. `UC_SECURITY_THREAT_MODEL.md`
5. `UC_TEST_PLAN.md`
6. `UC_INTEGRATION_TEST_REPORT.md`
7. `UC_METRICS_AND_ACCEPTANCE.md`
8. `UC_TRACEABILITY_MATRIX.md`
9. `UC_FAILURE_REGISTER.md`
10. `UC_REMEDIATION_PLAN.md`
11. `UC_TECHNICAL_PROCESS_MANUAL_AUDIT.md` — validación del Manual Técnico de Procesos AGI (UC-313/315/322/324/326/329/087)

## Resultado actual

- 61 UCs inspeccionadas.
- 48 UCs con tests que pasan.
- 1 UC con fallos por dependencia faltante (`google.adk` en UC-281).
- 12 UCs sin tests.

Ejecutar validación:

```bash
cd /Users/utron/Documents/code-books/TomoIII
python3 UC_VALIDATION/inventory.py
python3 UC_VALIDATION/generate_reports.py
python3 UC_VALIDATION/run_uc_tests.py
python3 UC_VALIDATION/generate_integration_report.py
```
