"""Escaneo defensivo de PII, secretos, URLs externas y operaciones destructivas.

Este script es solo auditoría: detecta y reporta, no modifica nada.
Excluye entornos virtuales, cachés y repositorios git.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path("/Users/utron/Documents/code-books/TomoIII")
OUTPUT = Path("/Users/utron/Documents/code-books/TomoIII/UC_VALIDATION/security_scan_results.json")

EXCLUDED_DIRS = {".venv", "venv", "__pycache__", ".git", "node_modules", ".pytest_cache", "dist", "build"}
EXCLUDED_FILES = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".db", ".bin", ".parquet", ".lock", ".md", ".txt", ".rst", ".log", ".csv"}
# Incluir archivos sin extensión (scripts shebang, .env, .xcscheme, etc.)
ALLOWED_SUFFIXES = {".py", ".yaml", ".yml", ".json", ".cfg", ".ini", ".env", ".swift", ".js", ".ts", ".jsx", ".tsx", ".xcscheme", ".xcconfig", ".plist", ".toml", ".sh", ".bash"}

PATTERNS: List[Dict[str, Any]] = [
    {
        "category": "secret_like",
        "name": "API key / token assignment",
        "regex": re.compile(r"(?i)(api[_-]?key|apikey|secret[_-]?key|password|token|auth[_-]?token)\s*[:=]\s*['\"][^'\"]{8,}", re.IGNORECASE),
        "severity": "P1",
    },
    {
        "category": "secret_like",
        "name": "AWS-like access key",
        "regex": re.compile(r"AKIA[0-9A-Z]{16}"),
        "severity": "P1",
    },
    {
        "category": "secret_like",
        "name": "Private key block",
        "regex": re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
        "severity": "P1",
    },
    {
        "category": "external_url",
        "name": "External HTTP(S) URL",
        "regex": re.compile(r"https?://[^\\s\\'\"\\)]+"),
        "severity": "P2",
        "ignore": re.compile(r"localhost|127\.0\.0\.1|0\.0\.0\.0|example\.(com|org)|github\.com|pypi\.org|docs\.python\.org|flask\.palletsprojects|docs\.openai|w3\.org"),
    },
    {
        "category": "destructive_op",
        "name": "Potentially destructive shell pattern",
        "regex": re.compile(r"(?i)(rm\s+-rf\s+/|DROP\s+TABLE|os\.system|subprocess\.call|eval\(|exec\(|shell=True)"),
        "severity": "P2",
    },
    {
        "category": "financial_side_effect",
        "name": "Real broker/exchange keyword",
        "regex": re.compile(r"(?i)(alpaca|binance|coinbase|kraken|ibkr|interactive\s*brokers|td\s*ameritrade|robinhood|schwab|fidelity|real\s*order|live\s*trading|production\s*api)"),
        "severity": "P2",
    },
]


def _should_skip(path: Path) -> bool:
    if path.name in EXCLUDED_DIRS or path.suffix.lower() in EXCLUDED_FILES:
        return True
    for part in path.parts:
        if part in EXCLUDED_DIRS:
            return True
    # Solo escanear archivos de código/configuración y scripts sin extensión
    if path.suffix.lower() not in ALLOWED_SUFFIXES and path.suffix != "":
        return True
    return False


def scan() -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    files_scanned = 0
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if _should_skip(p):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        files_scanned += 1
        lines = text.splitlines()
        for line_no, line in enumerate(lines, start=1):
            for pat in PATTERNS:
                if pat.get("ignore") and pat["ignore"].search(line):
                    continue
                for m in pat["regex"].finditer(line):
                    findings.append({
                        "file": str(p),
                        "line": line_no,
                        "category": pat["category"],
                        "name": pat["name"],
                        "severity": pat["severity"],
                        "match": line[m.start():m.end()].strip()[:120],
                        "context": line.strip()[:200],
                    })

    summary: Dict[str, Any] = {}
    for sev in ("P1", "P2", "P3"):
        summary[sev] = sum(1 for f in findings if f["severity"] == sev)
    summary["by_category"] = {}
    for f in findings:
        summary["by_category"][f["category"]] = summary["by_category"].get(f["category"], 0) + 1
    summary["files_scanned"] = files_scanned

    return {"summary": summary, "findings": findings}


if __name__ == "__main__":
    result = scan()
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))
    print(f"\nResultados guardados en {OUTPUT}")
