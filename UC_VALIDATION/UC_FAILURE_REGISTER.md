# UC_FAILURE_REGISTER.md

## Registro de fallos de interoperabilidad y gobernanza

| ID | Título | Severidad | UC | Componente | Causa raíz | Corrección propuesta | Estado |
|---|---|---|---|---|---|---|---|
| F-001 | Endpoints sin contrato declarativo | P2 | Varios | API | INPUT_CARDS ausente | Formalizar INPUT_CARDS y validar schema | abierto |
| F-002 | Auditoría dinámica de leakage no automatizada | P1 | UC financieros | datos | falta de tests walk-forward | Implementar validación temporal por UC | abierto |
| F-003 | Tests de seguridad adversariales no uniformes | P2 | Varios | tests | cobertura desigual | Plantilla de tests de contrato + seguridad por endpoint | abierto |
| F-004 | Dependencia de .venv locales sin requirements consolidado | P3 | Varios | entorno | reproducibilidad | Documentar requirements.lock por UC | abierto |
| F-005 | Integración cross-UC no probada end-to-end | P1 | Transversal | flujo | APIs independientes | Crear suite de integración cross-UC | abierto |
