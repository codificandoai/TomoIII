"""
UC-329 — Helper para importar módulos canónicos de UC-315/UC-325/UC-326/UC-328.

Uso:
    import _import_paths  # noqa: F401
    from central_brain import CentralBrain

O desde línea de comandos:
    PYTHONPATH=../../UC-326/code:../../UC-328/code:../../UC-325/code:../../UC-315/code python3 UC-329.py
"""

import sys
import os

_paths = [
    os.path.join(os.path.dirname(__file__), "..", "..", "UC-315", "code"),
    os.path.join(os.path.dirname(__file__), "..", "..", "UC-325", "code"),
    os.path.join(os.path.dirname(__file__), "..", "..", "UC-326", "code"),
    os.path.join(os.path.dirname(__file__), "..", "..", "UC-328", "code"),
]

for _path in _paths:
    _abs = os.path.abspath(_path)
    if _abs not in sys.path and os.path.isdir(_abs):
        sys.path.insert(0, _abs)
