"""Tests adicionales / smoke tests de UC-292."""
from __future__ import annotations

from agent_run import main


def test_cli_help():
    # Simula argv vacío y verifica que no lance excepción
    try:
        rc = main([])
    except SystemExit as exc:
        rc = exc.code
    assert rc == 1
