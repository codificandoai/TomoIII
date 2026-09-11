#!/usr/bin/env python3
"""Generate validation markdown artifacts from uc_inventory.json."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path("/Users/utron/Documents/code-books/TomoIII")
INV_PATH = ROOT / "UC_VALIDATION" / "uc_inventory.json"
OUT_DIR = ROOT / "UC_VALIDATION"


def load_inventory() -> list[dict]:
    with open(INV_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def uc_readme(uc: str) -> str:
    md = ROOT / uc / f"{uc}.md"
    if md.exists():
        return md.read_text(encoding="utf-8", errors="ignore")
    return ""


def title_from_readme(uc: str) -> str:
    text = uc_readme(uc)
    lines = text.splitlines()[:10]
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:120]
    return ""


def write_interoperability_map(inv: list[dict]) -> None:
    md = ["# UC_INTEROPERABILITY_MAP.md", ""]
    md.append("## 1. Inventario de UCs")
    md.append("")
    md.append("| UC | Responsabilidad | API Files | Tests | venv |")
    md.append("|---|---|---|---|---|")
    for item in inv:
        uc = item["uc"]
        title = title_from_readme(uc) or item["readme_preview"][:100]
        apis = ", ".join(item["api_files"]) or "-"
        tests = str(len(item["tests"]))
        venv = "yes" if item["has_venv"] else "no"
        md.append(f"| {uc} | {title} | {apis} | {tests} | {venv} |")
    md.append("")
    md.append("## 2. Mapa de endpoints por UC")
    md.append("")
    md.append("| UC | Método | Ruta | Contrato declarado |")
    md.append("|---|---|---|---|")
    for item in inv:
        uc = item["uc"]
        for route in item["routes"]:
            key = f"{route['method']} {route['path']}"
            has_card = "yes" if key in item["input_card_keys"] else "no"
            md.append(f"| {uc} | {route['method']} | `{route['path']}` | {has_card} |")
    md.append("")
    md.append("## 3. Flujo vertical end-to-end")
    md.append("")
    md.append("```text")
    md.append("Datos (UC-292/UC-294) → normalización (UC-309/UC-703) → RAG/memoria (UC-251/UC-296/UC-329)")
    md.append("  → análisis fundamental/técnico (UC-701/UC-702) → predicción ASK/BID (UC-279/UC-280/UC-283)")
    md.append("  → razonamiento (UC-314/UC-315/UC-322) → HITL (UC-290) → gateway (UC-300)")
    md.append("  → autorización/RBAC (UC-703 rbac_audit) → ejecución simulada (UC-317/UC-703 production_serving)")
    md.append("  → observación (UC-309/UC-308) → auditoría (UC-703 audit_ledger) → feedback (UC-087/UC-703 feedback_loop)")
    md.append("  → post-mortem (UC-703 postmortem_loop) → entrenamiento continuo (UC-075/UC-179/UC-320)")
    md.append("```")
    md.append("")
    md.append("## 4. Flujos horizontales clave")
    md.append("")
    md.append("| Origen | Destino | Propósito |")
    md.append("|---|---|---|")
    md.append("| UC-315 (orquestador cognitivo) | UC-290 (HITL guardian) | revisión antes de ejecución |")
    md.append("| UC-290 (HITL) | UC-300 (secure gateway) | capability token con dossier_hash |")
    md.append("| UC-300 (gateway) | UC-317 / UC-703 (runtime/ejecución) | ejecución autorizada en sandbox |")
    md.append("| UC-317 / UC-703 | UC-309 (observability) | métricas, trazas y logs |")
    md.append("| UC-309 / UC-703 | UC-703 (audit_ledger) | registro inmutable |")
    md.append("| UC-703 (postmortem_loop) | UC-703 (feedback_loop) | casos anti-regresión |")
    md.append("| UC-075 / UC-179 / UC-320 | UC-317 / UC-703 | promoción canary de modelos |")
    md.append("| UC-324 (contención) | UC-315 / UC-317 / UC-300 | kill switch y rollback |")
    md.append("")
    md.append("## 5. Matriz de dependencias entre UCs")
    md.append("")
    md.append("| Consumidor | Productor | Tipo | Notas |")
    md.append("|---|---|---|---|")
    md.append("| UC-290 HITL | UC-315 decisiones | request | requiere dossier + confidence |")
    md.append("| UC-300 gateway | UC-290 approval | token | capability_token one-use TTL |")
    md.append("| UC-317 runtime | UC-300 token | execution | sandbox, dry-run |")
    md.append("| UC-703 serving | UC-703 RBAC | authz | roles/scopes + rate limit |")
    md.append("| UC-703 postmortem | UC-703 serving/observability | events | registros inmutables |")
    md.append("| UC-075 training | UC-087 feedback | data | HITL labels + golden dataset |")
    md.append("| UC-320 LoRA/quant | UC-075/UC-179 | artifact | release gate |")
    md.append("")
    (OUT_DIR / "UC_INTEROPERABILITY_MAP.md").write_text("\n".join(md), encoding="utf-8")


def write_contract_matrix(inv: list[dict]) -> None:
    md = ["# UC_API_CONTRACT_MATRIX.md", ""]
    md.append("## Matriz de endpoints y declaración de contrato")
    md.append("")
    md.append("| UC | Endpoint | Declarado | Notas |")
    md.append("|---|---|---|---|")
    for item in inv:
        uc = item["uc"]
        for route in item["routes"]:
            key = f"{route['method']} {route['path']}"
            declared = "yes" if key in item["input_card_keys"] else "no"
            notes = "auto-doc INPUT_CARDS" if declared else "contrato implícito; formalizar"
            md.append(f"| {uc} | `{route['method']} {route['path']}` | {declared} | {notes} |")
    md.append("")
    md.append("## Observaciones")
    md.append("")
    total_routes = sum(len(i["routes"]) for i in inv)
    declared_routes = sum(1 for i in inv for r in i["routes"] if f"{r['method']} {r['path']}" in i["input_card_keys"])
    md.append(f"- Total de rutas detectadas: {total_routes}")
    md.append(f"- Rutas con contrato declarado (INPUT_CARDS): {declared_routes} ({100*declared_routes/total_routes:.1f}%)")
    md.append("- Los endpoints sin INPUT_CARDS declarativo deben ser formalizados para cumplir con pruebas de contrato automatizables.")
    md.append("")
    (OUT_DIR / "UC_API_CONTRACT_MATRIX.md").write_text("\n".join(md), encoding="utf-8")


def write_data_lineage(inv: list[dict]) -> None:
    md = ["# UC_DATA_LINEAGE_AND_LEAKAGE_AUDIT.md", ""]
    md.append("## Supuesto de auditoría")
    md.append("")
    md.append("Esta auditoría se basa en la inspección de documentación y contratos. No sustituye a una auditoría dinámica completa de series temporales.")
    md.append("")
    md.append("## Controles de data leakage declarados por UC")
    md.append("")
    md.append("| UC | Controles observados | Riesgos residuales |")
    md.append("|---|---|---|")
    patterns = {
        "leakage": "revisión de leakage",
        "look-ahead": "look-ahead bias",
        "survivorship": "survivorship bias",
        "temporal": "validación temporal",
        "split": "split por tiempo",
    }
    for item in inv:
        uc = item["uc"]
        text = uc_readme(uc).lower()
        controls = []
        risks = []
        if "leakage" in text:
            controls.append("menciona leakage")
        if "temporal" in text or "time-based" in text:
            controls.append("validación temporal")
        if "train" in text and "test" in text:
            controls.append("train/test")
        if not controls:
            risks.append("no documenta explícitamente controles de leakage temporal")
        md.append(f"| {uc} | {'; '.join(controls) or 'ninguno documentado'} | {'; '.join(risks) or 'auditoría dinámica pendiente'} |")
    md.append("")
    md.append("## Recomendaciones")
    md.append("")
    md.append("1. Formalizar en cada UC-XXX.md la descripción del split temporal, la fecha de corte y el horizonte de predicción.")
    md.append("2. Implementar tests automatizados de leakage por UC que validen que no se usan features futuras.")
    md.append("3. Etiquetar cada dato con `origin_timestamp`, `available_timestamp` y `market_session`.")
    md.append("4. Ejecutar pruebas de backtest walk-forward independientes del entrenamiento.")
    md.append("")
    (OUT_DIR / "UC_DATA_LINEAGE_AND_LEAKAGE_AUDIT.md").write_text("\n".join(md), encoding="utf-8")


def write_security_threat_model(inv: list[dict]) -> None:
    md = ["# UC_SECURITY_THREAT_MODEL.md", ""]
    md.append("## Amenazas y controles observados")
    md.append("")
    md.append("| Amenaza | UCs con control | Estado |")
    md.append("|---|---|---|")
    md.append("| Inyección de prompt | UC-119, UC-290, UC-300, UC-703 guardrails | implementado parcial |")
    md.append("| Escalamiento de privilegios | UC-300, UC-703 rbac_audit | implementado |")
    md.append("| Ejecución no autorizada | UC-290, UC-300, UC-703 approval_workflow | implementado |")
    md.append("| Falsificación de action_hash / approval_ref | UC-300 capability_token, UC-703 audit_ledger | implementado |")
    md.append("| Data poisoning / envenenamiento | UC-119, UC-308, UC-703 postmortem_loop | revisión periódica |")
    md.append("| Exfiltración de PII/secrets | UC-119, UC-290, UC-703 guardrails | revisar logs |")
    md.append("| SSRF en tool calls | UC-300 allowlist, UC-324 sandbox | implementado |")
    md.append("| Condición de carrera en aprobaciones | UC-300 TOCTOU, UC-703 approval workflow | implementado |")
    md.append("")
    md.append("## Controles transversales")
    md.append("")
    md.append("- RBAC/ABAC en UC-300 y UC-703.")
    md.append("- HITL con dossier_hash en UC-290.")
    md.append("- Capability tokens TTL y one-use en UC-300.")
    md.append("- Ledger inmutable con hash-chain en UC-703.")
    md.append("- Sandbox y kill switch en UC-324.")
    md.append("- Observabilidad en UC-309/UC-703.")
    md.append("")
    (OUT_DIR / "UC_SECURITY_THREAT_MODEL.md").write_text("\n".join(md), encoding="utf-8")


def write_test_plan(inv: list[dict]) -> None:
    md = ["# UC_TEST_PLAN.md", ""]
    md.append("## Plan de pruebas reproducible")
    md.append("")
    md.append("### Fases")
    md.append("1. Fase 1: descubrimiento (inventory.py) → `UC_VALIDATION/uc_inventory.json`")
    md.append("2. Fase 2: pruebas de contrato por endpoint usando INPUT_CARDS")
    md.append("3. Fase 3: integración entre UCs (flujo vertical/horizontal)")
    md.append("4. Fase 4: validación de datos y predicción")
    md.append("5. Fase 5: pruebas de seguridad con payloads adversariales")
    md.append("6. Fase 6: caos y carga")
    md.append("")
    md.append("### Comando de ejecución por UC")
    md.append("```bash")
    md.append("cd UC-XXX/code && python -m pytest tests -q")
    md.append("```")
    md.append("")
    md.append("### UCs con tests existentes")
    md.append("")
    md.append("| UC | Nº tests | Notas |")
    md.append("|---|---|---|")
    for item in inv:
        md.append(f"| {item['uc']} | {len(item['tests'])} | {'; '.join(item['tests'][:3])}{'...' if len(item['tests'])>3 else ''} |")
    md.append("")
    md.append("### Próximas pruebas a implementar")
    md.append("- Generador de contratos a partir de INPUT_CARDS.")
    md.append("- Tests adversariales para cada endpoint de UC-290/UC-300/UC-703.")
    md.append("- Validación de hash-chain del ledger.")
    md.append("- Walk-forward leakage tests en UCs financieras.")
    md.append("")
    (OUT_DIR / "UC_TEST_PLAN.md").write_text("\n".join(md), encoding="utf-8")


def write_metrics_acceptance(inv: list[dict]) -> None:
    md = ["# UC_METRICS_AND_ACCEPTANCE.md", ""]
    md.append("## Métricas y criterios de aceptación")
    md.append("")
    md.append("### Métricas financieras/predictivas")
    md.append("- MAE/RMSE de ASK y BID por separado.")
    md.append("- Error absoluto y relativo de spread.")
    md.append("- Directional accuracy, precision/recall/F1.")
    md.append("- Calibration error y cobertura de intervalos.")
    md.append("- Quantile loss por horizonte.")
    md.append("- Error condicional por régimen de volatilidad.")
    md.append("")
    md.append("### Métricas operativas")
    md.append("- Latencia p50/p95/p99 de inferencia.")
    md.append("- Throughput de requests por segundo.")
    md.append("- Tasa de rechazo por guardrails.")
    md.append("- MTTD, MTTR y tasa de recurrencia.")
    md.append("- Cobertura de decisiones con dossier aprobado.")
    md.append("")
    md.append("### Criterios de aceptación")
    md.append("- Ninguna ejecución sin capability token válido.")
    md.append("- Hash-chain de auditoría verificable.")
    md.append("- Test de contrato pasa >90% de endpoints.")
    md.append("- No leakage detectado en pruebas temporales.")
    md.append("- Rollback probado en sandbox.")
    md.append("")
    (OUT_DIR / "UC_METRICS_AND_ACCEPTANCE.md").write_text("\n".join(md), encoding="utf-8")


def write_traceability(inv: list[dict]) -> None:
    md = ["# UC_TRACEABILITY_MATRIX.md", ""]
    md.append("| Requisito | UC | Endpoints | Tests | Evidencia |")
    md.append("|---|---|---|---|---|")
    for item in inv:
        uc = item["uc"]
        endpoints = ", ".join(f"{r['method']} {r['path']}" for r in item["routes"][:3])
        if len(item["routes"]) > 3:
            endpoints += "..."
        tests = ", ".join(item["tests"][:2]) or "-"
        if len(item["tests"]) > 2:
            tests += "..."
        md.append(f"| {item['readme_preview'][:80]} | {uc} | {endpoints} | {tests} | {uc}/{uc}.md |")
    md.append("")
    (OUT_DIR / "UC_TRACEABILITY_MATRIX.md").write_text("\n".join(md), encoding="utf-8")


def write_failure_register(inv: list[dict]) -> None:
    md = ["# UC_FAILURE_REGISTER.md", ""]
    md.append("## Registro de fallos de interoperabilidad y gobernanza")
    md.append("")
    md.append("| ID | Título | Severidad | UC | Componente | Causa raíz | Corrección propuesta | Estado |")
    md.append("|---|---|---|---|---|---|---|---|")
    md.append("| F-001 | Endpoints sin contrato declarativo | P2 | Varios | API | INPUT_CARDS ausente | Formalizar INPUT_CARDS y validar schema | abierto |")
    md.append("| F-002 | Auditoría dinámica de leakage no automatizada | P1 | UC financieros | datos | falta de tests walk-forward | Implementar validación temporal por UC | abierto |")
    md.append("| F-003 | Tests de seguridad adversariales no uniformes | P2 | Varios | tests | cobertura desigual | Plantilla de tests de contrato + seguridad por endpoint | abierto |")
    md.append("| F-004 | Dependencia de .venv locales sin requirements consolidado | P3 | Varios | entorno | reproducibilidad | Documentar requirements.lock por UC | abierto |")
    md.append("| F-005 | Integración cross-UC no probada end-to-end | P1 | Transversal | flujo | APIs independientes | Crear suite de integración cross-UC | abierto |")
    md.append("")
    (OUT_DIR / "UC_FAILURE_REGISTER.md").write_text("\n".join(md), encoding="utf-8")


def write_remediation_plan(inv: list[dict]) -> None:
    md = ["# UC_REMEDIATION_PLAN.md", ""]
    md.append("## Plan de correcciones priorizadas")
    md.append("")
    md.append("| Prioridad | Acción | UCs afectadas | Owner sugerido | Prueba de regresión |")
    md.append("|---|---|---|---|---|")
    md.append("| P0 | Asegurar que toda ejecución requiera capability_token validado | UC-300, UC-317, UC-703 | arquitectura seguridad | test de ejecución sin token rechazada |")
    md.append("| P1 | Implementar suite cross-UC de flujo vertical | UC-290→300→317→309→703 | integración | test end-to-end con trace_id |")
    md.append("| P1 | Añadir tests de leakage temporal | UC-279, UC-701, UC-702, UC-292 | ciencia de datos | test walk-forward falla si usa features futuras |")
    md.append("| P2 | Formalizar INPUT_CARDS en endpoints sin contrato | todas con api_*.py | API owner | test de contrato pasa |")
    md.append("| P2 | Unificar exportación de métricas a Prometheus/Loki/Tempo | UC-309, UC-703, UC-075 | observability | dashboard muestra métricas |")
    md.append("| P3 | Consolidar requirements.lock por UC | todas con .venv | DevOps | CI reproduce entorno |")
    md.append("")
    (OUT_DIR / "UC_REMEDIATION_PLAN.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    inv = load_inventory()
    write_interoperability_map(inv)
    write_contract_matrix(inv)
    write_data_lineage(inv)
    write_security_threat_model(inv)
    write_test_plan(inv)
    write_metrics_acceptance(inv)
    write_traceability(inv)
    write_failure_register(inv)
    write_remediation_plan(inv)
    print(f"Generated {len(list(OUT_DIR.glob('*.md')))} markdown artifacts in {OUT_DIR}")
