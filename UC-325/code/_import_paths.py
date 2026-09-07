"""
UC-325 — Helper para importar módulos de UC-315 desde su ubicación canónica.

Uso:
    import _import_paths  # noqa: F401
    from central_brain import CentralBrain  # ahora disponible

O desde la línea de comandos:
    PYTHONPATH=../../UC-315/code python3 UC-325.py
"""

import sys
import os

_uc315_path = os.path.join(os.path.dirname(__file__), "..", "..", "UC-315", "code")
_uc315_abs = os.path.abspath(_uc315_path)

if _uc315_abs not in sys.path and os.path.isdir(_uc315_abs):
    sys.path.insert(0, _uc315_abs)
