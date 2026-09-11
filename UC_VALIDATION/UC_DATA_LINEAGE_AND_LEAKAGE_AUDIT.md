# UC_DATA_LINEAGE_AND_LEAKAGE_AUDIT.md

## Supuesto de auditoría

Esta auditoría se basa en la inspección de documentación y contratos. No sustituye a una auditoría dinámica completa de series temporales.

## Controles de data leakage declarados por UC

| UC | Controles observados | Riesgos residuales |
|---|---|---|
| UC-075 | train/test | auditoría dinámica pendiente |
| UC-083 | validación temporal | auditoría dinámica pendiente |
| UC-087 | train/test | auditoría dinámica pendiente |
| UC-119 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-127 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-129 | validación temporal | auditoría dinámica pendiente |
| UC-162 | validación temporal; train/test | auditoría dinámica pendiente |
| UC-179 | train/test | auditoría dinámica pendiente |
| UC-251 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-257 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-258 | train/test | auditoría dinámica pendiente |
| UC-259 | validación temporal; train/test | auditoría dinámica pendiente |
| UC-260 | train/test | auditoría dinámica pendiente |
| UC-261 | train/test | auditoría dinámica pendiente |
| UC-262 | train/test | auditoría dinámica pendiente |
| UC-263 | train/test | auditoría dinámica pendiente |
| UC-264 | train/test | auditoría dinámica pendiente |
| UC-265 | train/test | auditoría dinámica pendiente |
| UC-266 | train/test | auditoría dinámica pendiente |
| UC-268 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-269 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-270 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-271 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-272 | validación temporal; train/test | auditoría dinámica pendiente |
| UC-273 | validación temporal | auditoría dinámica pendiente |
| UC-274 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-275 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-276 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-277 | validación temporal | auditoría dinámica pendiente |
| UC-279 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-280 | train/test | auditoría dinámica pendiente |
| UC-281 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-283 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-284 | validación temporal | auditoría dinámica pendiente |
| UC-289 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-290 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-292 | validación temporal; train/test | auditoría dinámica pendiente |
| UC-293 | train/test | auditoría dinámica pendiente |
| UC-294 | train/test | auditoría dinámica pendiente |
| UC-295 | train/test | auditoría dinámica pendiente |
| UC-296 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-300 | validación temporal | auditoría dinámica pendiente |
| UC-307 | train/test | auditoría dinámica pendiente |
| UC-308 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-309 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-313 | validación temporal; train/test | auditoría dinámica pendiente |
| UC-314 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-315 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-317 | validación temporal | auditoría dinámica pendiente |
| UC-320 | menciona leakage; validación temporal; train/test | auditoría dinámica pendiente |
| UC-322 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-324 | menciona leakage | auditoría dinámica pendiente |
| UC-325 | validación temporal | auditoría dinámica pendiente |
| UC-326 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-328 | validación temporal | auditoría dinámica pendiente |
| UC-329 | validación temporal | auditoría dinámica pendiente |
| UC-330 | validación temporal | auditoría dinámica pendiente |
| UC-700 | validación temporal; train/test | auditoría dinámica pendiente |
| UC-701 | validación temporal | auditoría dinámica pendiente |
| UC-702 | ninguno documentado | no documenta explícitamente controles de leakage temporal |
| UC-703 | menciona leakage; validación temporal; train/test | auditoría dinámica pendiente |

## Recomendaciones

1. Formalizar en cada UC-XXX.md la descripción del split temporal, la fecha de corte y el horizonte de predicción.
2. Implementar tests automatizados de leakage por UC que validen que no se usan features futuras.
3. Etiquetar cada dato con `origin_timestamp`, `available_timestamp` y `market_session`.
4. Ejecutar pruebas de backtest walk-forward independientes del entrenamiento.
