"""
UC-326 — Helper para importar módulos de UC-315/UC-325 desde sus ubicaciones canónicas.

Uso:
    import _import_paths  # noqa: F401
    from central_brain import CentralBrain

O desde la línea de comandos:
    PYTHONPATH=../../UC-325/code:../../UC-315/code python3 UC-326.py
"""

import sys
import os

_uc315_path = os.path.join(os.path.dirname(__file__), "..", "..", "UC-315", "code")
_uc325_path = os.path.join(os.path.dirname(__file__), "..", "..", "UC-325", "code")

for _path in [_uc315_path, _uc325_path]:
    _abs = os.path.abspath(_path)
    if _abs not in sys.path and os.path.isdir(_abs):
        sys.path.insert(0, _abs)
