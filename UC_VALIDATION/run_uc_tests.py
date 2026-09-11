#!/usr/bin/env python3
"""Run pytest in each UC code directory and collect results."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path("/Users/utron/Documents/code-books/TomoIII")
OUT = ROOT / "UC_VALIDATION" / "uc_test_results.json"


def run_tests(uc: str) -> dict:
    code_dir = ROOT / uc / "code"
    if not (code_dir / "tests").exists() and not (code_dir / f"tests_{uc.split('-')[1]}").exists():
        return {"uc": uc, "status": "no_tests", "passed": None, "failed": None, "output": ""}

    # choose test dir
    test_dir = code_dir / "tests"
    if not test_dir.exists():
        test_dir = code_dir / f"tests_{uc.split('-')[1]}"

    env = os.environ.copy()
    # prefer global pytest/python; isolated per UC unless .venv present
    python = "python"
    venv = code_dir / ".venv"
    if venv.exists():
        env["PATH"] = str(venv / "bin") + os.pathsep + env["PATH"]
        python = str(venv / "bin" / "python")

    try:
        result = subprocess.run(
            [python, "-m", "pytest", str(test_dir), "-q", "-W", "ignore"],
            cwd=str(code_dir),
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        stdout = result.stdout + result.stderr
        # parse last line like 252 passed or 10 failed
        m = None
        for line in reversed(stdout.splitlines()):
            m = __import__("re").search(r"(\d+)\s+passed", line)
            if m:
                break
        passed = int(m.group(1)) if m else None
        failed = None
        fm = None
        for line in reversed(stdout.splitlines()):
            fm = __import__("re").search(r"(\d+)\s+failed", line)
            if fm:
                break
        failed = int(fm.group(1)) if fm else 0
        return {
            "uc": uc,
            "status": "ok" if result.returncode == 0 else "fail",
            "passed": passed,
            "failed": failed,
            "output": stdout[-2000:],
        }
    except subprocess.TimeoutExpired as e:
        return {"uc": uc, "status": "timeout", "passed": None, "failed": None, "output": str(e)[-500:]}
    except Exception as e:
        return {"uc": uc, "status": "error", "passed": None, "failed": None, "output": str(e)[-500:]}


def main() -> None:
    ucs = sorted(p.name for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("UC-"))
    results = []
    for uc in ucs:
        print(f"Running {uc}...", flush=True)
        results.append(run_tests(uc))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Wrote results to {OUT}")


if __name__ == "__main__":
    main()
