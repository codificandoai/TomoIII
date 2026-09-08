#!/usr/bin/env python3
"""Standalone validation suite for UC-309."""
from __future__ import annotations

import os
import subprocess
import sys
import compileall


def validate():
    code_dir = os.path.dirname(os.path.abspath(__file__))
    print("[validate_uc309] compileall ...")
    ok = compileall.compile_dir(code_dir, quiet=True, force=True)
    if not ok:
        return 1

    print("[validate_uc309] parse YAML/JSON ...")
    try:
        from UC_309 import validate_all
    except ImportError:
        # If running directly, import from local package
        import importlib.util
        spec = importlib.util.spec_from_file_location("UC_309_cli", os.path.join(code_dir, "UC-309.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod.validate_all()
    return validate_all()


def run_pytest():
    tests_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests_uc309")
    if not os.path.isdir(tests_dir):
        print("[validate_uc309] no tests directory")
        return 0
    print("[validate_uc309] pytest ...")
    rc = subprocess.call([sys.executable, "-m", "pytest", tests_dir, "-q", "--tb=short"])
    return rc


def main():
    rc = validate()
    if rc != 0:
        return rc
    return run_pytest()


if __name__ == "__main__":
    sys.exit(main())
