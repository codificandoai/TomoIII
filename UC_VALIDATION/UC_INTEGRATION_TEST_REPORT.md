# UC_INTEGRATION_TEST_REPORT.md

## Resumen

- UCs inspeccionadas: 61
- UCs con tests que pasan: 48
- UCs sin tests: 12
- UCs con fallos: 1
- Tests aprobados totales (UCs OK): 2729

## Resultados por UC

| UC | Estado | Pasados | Fallidos | Notas |
|---|---|---|---|---|
| UC-075 | ok | 167 | 0 |  |
| UC-083 | no_tests | - | - | sin directorio de tests |
| UC-087 | ok | 31 | 0 |  |
| UC-119 | ok | 44 | 0 |  |
| UC-127 | ok | 51 | 0 |  |
| UC-129 | ok | 46 | 0 |  |
| UC-162 | no_tests | - | - | sin directorio de tests |
| UC-179 | ok | 70 | 0 |  |
| UC-251 | ok | 29 | 0 |  |
| UC-257 | ok | 17 | 0 |  |
| UC-258 | ok | 18 | 0 |  |
| UC-259 | ok | 23 | 0 |  |
| UC-260 | ok | 18 | 0 |  |
| UC-261 | ok | 20 | 0 |  |
| UC-262 | ok | 11 | 0 |  |
| UC-263 | ok | 14 | 0 |  |
| UC-264 | ok | 15 | 0 |  |
| UC-265 | ok | 33 | 0 |  |
| UC-266 | ok | 38 | 0 |  |
| UC-268 | ok | 19 | 0 |  |
| UC-269 | ok | 11 | 0 |  |
| UC-270 | ok | 22 | 0 |  |
| UC-271 | ok | 32 | 0 |  |
| UC-272 | ok | 36 | 0 |  |
| UC-273 | ok | 59 | 0 |  |
| UC-274 | ok | 69 | 0 |  |
| UC-275 | ok | 78 | 0 |  |
| UC-276 | ok | 78 | 0 |  |
| UC-277 | ok | 93 | 0 |  |
| UC-279 | ok | 26 | 0 |  |
| UC-280 | ok | 19 | 0 |  |
| UC-281 | fail | 7 | 5 | d - Asserti... FAILED tests/test_orchestrator.py::test_events_cover_barrier - assert 4 == 5 5 failed, 7 passed in 0.71s  |
| UC-283 | ok | 11 | 0 |  |
| UC-284 | ok | 11 | 0 |  |
| UC-289 | ok | 13 | 0 |  |
| UC-290 | no_tests | - | - | sin directorio de tests |
| UC-292 | ok | 47 | 0 |  |
| UC-293 | ok | 61 | 0 |  |
| UC-294 | ok | 70 | 0 |  |
| UC-295 | ok | 82 | 0 |  |
| UC-296 | ok | 91 | 0 |  |
| UC-300 | no_tests | - | - | sin directorio de tests |
| UC-307 | ok | 30 | 0 |  |
| UC-308 | no_tests | - | - | sin directorio de tests |
| UC-309 | no_tests | - | - | sin directorio de tests |
| UC-313 | ok | 131 | 0 |  |
| UC-314 | ok | 19 | 0 |  |
| UC-315 | ok | 130 | 0 |  |
| UC-317 | ok | 44 | 0 |  |
| UC-320 | ok | 360 | 0 |  |
| UC-322 | no_tests | - | - | sin directorio de tests |
| UC-324 | ok | 110 | 0 |  |
| UC-325 | no_tests | - | - | sin directorio de tests |
| UC-326 | no_tests | - | - | sin directorio de tests |
| UC-328 | no_tests | - | - | sin directorio de tests |
| UC-329 | no_tests | - | - | sin directorio de tests |
| UC-330 | no_tests | - | - | sin directorio de tests |
| UC-700 | ok | 20 | 0 |  |
| UC-701 | ok | 18 | 0 |  |
| UC-702 | ok | 42 | 0 |  |
| UC-703 | ok | 252 | 0 |  |

## UCs con fallos

### UC-281
```text
ert events[0]["type"] == "run.started"
>       assert sum(e["type"] == "framework.completed" for e in events) == 5
E       assert 4 == 5
E        +  where 4 = sum(<generator object test_events_cover_barrier.<locals>.<genexpr> at 0x10b7f9560>)

tests/test_orchestrator.py:56: AssertionError
=========================== short test summary info ============================
FAILED tests/test_api.py::test_full_pipeline_api - ModuleNotFoundError: No mo...
FAILED tests/test_api.py::test_list_endpoints - ModuleNotFoundError: No modul...
FAILED tests/test_api.py::test_validation - ModuleNotFoundError: No module na...
FAILED tests/test_orchestrator.py::test_all_five_frameworks_respond - Asserti...
FAILED tests/test_orchestrator.py::test_events_cover_barrier - assert 4 == 5
5 failed, 7 passed in 0.71s

```

## UCs sin tests

UC-083, UC-162, UC-290, UC-300, UC-308, UC-309, UC-322, UC-325, UC-326, UC-328, UC-329, UC-330

## Recomendaciones
1. Instalar dependencia faltante `google.adk` en UC-281 o marcar tests como opcional.
2. Añadir tests mínimos a UCs sin cobertura, empezando por UC-290, UC-300, UC-308, UC-309.
3. Crear suite de integración cross-UC que valide flujo vertical con datos sintéticos.
4. Ejecutar este reporte periódicamente en CI con entornos reproducibles.
