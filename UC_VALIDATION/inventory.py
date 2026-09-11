#!/usr/bin/env python3
"""Inventory discovery for UC ecosystem."""
from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

ROOT = Path("/Users/utron/Documents/code-books/TomoIII")


def extract_routes(code: str) -> list[dict]:
    routes = []
    for line in code.splitlines():
        m = re.search(r"@app\.(\w+)\(['\"]([^'\"]+)['\"]", line)
        if m:
            routes.append({"method": m.group(1).upper(), "path": m.group(2)})
    return routes


def extract_input_cards(code: str) -> dict:
    m = re.search(r"INPUT_CARDS\s*=\s*(\{.*?\n\})", code, re.DOTALL)
    if not m:
        return {}
    try:
        parsed = ast.literal_eval(m.group(1))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def discover() -> list[dict]:
    ucs = sorted(p for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("UC-"))
    inventory = []
    for uc in ucs:
        md = uc / f"{uc.name}.md"
        readme_text = ""
        if md.exists():
            try:
                with open(md, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[:15]
                    readme_text = " ".join(l.strip() for l in lines)
            except Exception:
                pass
        code_dir = uc / "code"
        api_files = []
        if code_dir.exists():
            api_files = sorted([f.name for f in code_dir.iterdir() if f.is_file() and f.name.startswith("api_") and f.name.endswith(".py")])
        routes: list[dict] = []
        input_cards: dict = {}
        for af in api_files:
            try:
                with open(code_dir / af, "r", encoding="utf-8", errors="ignore") as f:
                    code = f.read()
                routes.extend(extract_routes(code))
                cards = extract_input_cards(code)
                input_cards.update(cards)
            except Exception:
                pass
        tests = []
        test_dir = uc / "code" / "tests"
        if test_dir.exists():
            tests = sorted([f.name for f in test_dir.iterdir() if f.name.startswith("test_") and f.name.endswith(".py")])
        inventory.append({
            "uc": uc.name,
            "readme_preview": readme_text[:250],
            "api_files": api_files,
            "routes": routes,
            "input_card_keys": list(input_cards.keys()),
            "tests": tests,
            "has_venv": (uc / "code" / ".venv").exists(),
        })
    return inventory


if __name__ == "__main__":
    inv = discover()
    out = ROOT / "UC_VALIDATION" / "uc_inventory.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(inv, f, indent=2, ensure_ascii=False)
    print(f"Wrote inventory for {len(inv)} UCs to {out}")
