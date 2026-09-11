"""Validación de puesta en marcha (startup) de APIs Flask por UC.

Cada api*.py se importa en un subproceso Python fresco para evitar colisiones
entre módulos con el mismo nombre en diferentes UCs. Se verifica:
- Que la aplicación Flask se instancia sin errores.
- Que el endpoint de salud responde 200 en modo test_client.
- Que /api/v1/schema responde 200 si existe.

No levanta servidores reales, por lo que no hay conflictos de puerto ni
efectos secundarios externos.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

RESULT_PATH = Path("/Users/utron/Documents/code-books/TomoIII/UC_VALIDATION/startup_validation_results.json")
INVENTORY_PATH = Path("/Users/utron/Documents/code-books/TomoIII/UC_VALIDATION/uc_inventory.json")
REPO_ROOT = Path("/Users/utron/Documents/code-books/TomoIII")

PROBE_SCRIPT = r'''
import json, sys, os
sys.path.insert(0, "{code_dir}")
{extra_paths}

try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("{module_name}", "{api_path}")
    if spec is None or spec.loader is None:
        print(json.dumps({{"import_ok": False, "error": "spec_none"}}))
        sys.exit(0)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    app = getattr(module, "app", None)
    if app is None and hasattr(module, "create_app"):
        app = module.create_app()
    if app is None:
        print(json.dumps({{"import_ok": False, "error": "no Flask app found"}}))
        sys.exit(0)

    app.config["TESTING"] = True
    client = app.test_client()

    def try_get(path):
        if not path:
            return None
        try:
            r = client.get(path)
            return {{"path": path, "status": r.status_code, "ok": r.status_code == 200}}
        except Exception as e:
            return {{"path": path, "status": None, "ok": False, "error": str(e)}}

    health = try_get("{health_path}")
    schema = try_get("{schema_path}")

    print(json.dumps({{
        "import_ok": True,
        "health": health,
        "schema": schema,
        "error": None,
    }}))
except Exception as e:
    print(json.dumps({{"import_ok": False, "error": type(e).__name__ + ": " + str(e)}}))
'''


def _health_path(routes: List[Dict[str, str]]) -> str:
    for r in routes:
        if r.get("path") == "/health" and r.get("method") == "GET":
            return "/health"
    for r in routes:
        if r.get("path") in ("/api/v1/health", "/health"):
            return r.get("path")
    return "/"


def _schema_path(routes: List[Dict[str, str]]) -> str:
    for r in routes:
        if r.get("path") == "/api/v1/schema" and r.get("method") == "GET":
            return "/api/v1/schema"
    return ""


def _python_executable(uc_dir: Path) -> str:
    candidates = [
        uc_dir / "code" / ".venv" / "bin" / "python3",
        uc_dir / ".venv" / "bin" / "python3",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return sys.executable


def validate_api(uc_dir: Path, api_file: str, routes: List[Dict[str, str]]) -> Dict[str, Any]:
    code_dir = uc_dir / "code"
    api_path = code_dir / api_file
    result: Dict[str, Any] = {
        "uc": uc_dir.name,
        "api_file": api_file,
        "import_ok": False,
        "health": None,
        "schema": None,
        "error": None,
    }

    if not api_path.exists():
        result["error"] = f"file not found: {api_path}"
        return result

    extras = [REPO_ROOT / "UC-315" / "code", REPO_ROOT / "UC-296" / "code"]
    extra_paths = "\n".join(f'sys.path.insert(0, "{p}")' for p in extras)

    module_name = f"{uc_dir.name}_{api_file.replace('.', '_')}"
    health = _health_path(routes)
    schema = _schema_path(routes)

    script = PROBE_SCRIPT.format(
        code_dir=str(code_dir),
        extra_paths=extra_paths,
        module_name=module_name,
        api_path=str(api_path),
        health_path=health,
        schema_path=schema,
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{code_dir}:{REPO_ROOT / 'UC-315' / 'code'}:{REPO_ROOT / 'UC-296' / 'code'}"

    proc = subprocess.run(
        [_python_executable(uc_dir), "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    try:
        data = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        data = {"import_ok": False, "error": (proc.stderr or proc.stdout)[:500]}

    result.update(data)
    return result


def main() -> None:
    if not INVENTORY_PATH.exists():
        print(f"Inventory not found: {INVENTORY_PATH}")
        sys.exit(1)

    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    results: List[Dict[str, Any]] = []

    for entry in inventory:
        uc = entry["uc"]
        uc_dir = REPO_ROOT / uc
        api_files = entry.get("api_files", [])
        routes = entry.get("routes", [])
        if not api_files:
            continue
        for api_file in api_files:
            if "venv" in api_file or ".venv" in str(api_file):
                continue
            print(f"Validando {uc} -> {api_file} ...")
            result = validate_api(uc_dir, api_file, routes)
            results.append(result)
            status = "OK" if result["import_ok"] and result.get("health", {}).get("ok") else "FAIL"
            print(f"  {status}: {result.get('error') or ''}")

    RESULT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResultados guardados en {RESULT_PATH}")

    total = len(results)
    ok = sum(1 for r in results if r["import_ok"] and r.get("health", {}).get("ok"))
    print(f"APIs validadas: {ok}/{total}")


if __name__ == "__main__":
    main()
