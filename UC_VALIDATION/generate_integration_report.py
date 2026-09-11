#!/usr/bin/env python3
"""Generate UC_INTEGRATION_TEST_REPORT.md from uc_test_results.json."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("/Users/utron/Documents/code-books/TomoIII")
OUT = ROOT / "UC_VALIDATION" / "UC_INTEGRATION_TEST_REPORT.md"

with open(ROOT / "UC_VALIDATION" / "uc_test_results.json", "r", encoding="utf-8") as f:
    results = json.load(f)

lines = ["# UC_INTEGRATION_TEST_REPORT.md", ""]
lines.append("## Resumen")
lines.append("")
total = len(results)
ok = sum(1 for r in results if r["status"] == "ok")
no_tests = sum(1 for r in results if r["status"] == "no_tests")
fail = sum(1 for r in results if r["status"] not in ("ok", "no_tests"))
lines.append(f"- UCs inspeccionadas: {total}")
lines.append(f"- UCs con tests que pasan: {ok}")
lines.append(f"- UCs sin tests: {no_tests}")
lines.append(f"- UCs con fallos: {fail}")
total_passed = sum((r.get("passed") or 0) for r in results if r["status"] == "ok")
lines.append(f"- Tests aprobados totales (UCs OK): {total_passed}")
lines.append("")
lines.append("## Resultados por UC")
lines.append("")
lines.append("| UC | Estado | Pasados | Fallidos | Notas |")
lines.append("|---|---|---|---|---|")
for r in results:
    notes = ""
    if r["status"] == "fail":
        notes = (r.get("output") or "")[-120:].replace("\n", " ")
    elif r["status"] == "no_tests":
        notes = "sin directorio de tests"
    elif r["status"] == "timeout":
        notes = "timeout"
    elif r["status"] == "error":
        notes = "error al ejecutar pytest"
    lines.append(
        f"| {r['uc']} | {r['status']} | {r.get('passed') if r.get('passed') is not None else '-'} | "
        f"{r.get('failed') if r.get('failed') is not None else '-'} | {notes} |"
    )
lines.append("")
lines.append("## UCs con fallos")
lines.append("")
for r in results:
    if r["status"] == "fail":
        lines.append(f"### {r['uc']}")
        lines.append("```text")
        lines.append(r.get("output", "")[-800:])
        lines.append("```")
        lines.append("")
lines.append("## UCs sin tests")
lines.append("")
lines.append(", ".join(r["uc"] for r in results if r["status"] == "no_tests"))
lines.append("")
lines.append("## Recomendaciones")
lines.append("1. Instalar dependencia faltante `google.adk` en UC-281 o marcar tests como opcional.")
lines.append("2. Añadir tests mínimos a UCs sin cobertura, empezando por UC-290, UC-300, UC-308, UC-309.")
lines.append("3. Crear suite de integración cross-UC que valide flujo vertical con datos sintéticos.")
lines.append("4. Ejecutar este reporte periódicamente en CI con entornos reproducibles.")
lines.append("")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {OUT}")
