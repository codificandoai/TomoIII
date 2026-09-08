"""
UC-290 — Helper para importar módulos canónicos de otras UC.

Uso:
    import _import_paths  # noqa: F401
    from model_guardian import ModelSecurityGuardian  # UC-087
"""

import sys
import os

_paths = [
    os.path.join(os.path.dirname(__file__), "..", "..", "UC-315", "code"),
    os.path.join(os.path.dirname(__file__), "..", "..", "UC-087", "code"),
    os.path.join(os.path.dirname(__file__), "..", "..", "UC-324", "code"),
    os.path.join(os.path.dirname(__file__), "..", "..", "UC-322", "code"),
    os.path.join(os.path.dirname(__file__), "..", "..", "UC-325", "code"),
    os.path.join(os.path.dirname(__file__), "..", "..", "UC-329", "code"),
    os.path.join(os.path.dirname(__file__), "..", "..", "UC-162", "code"),
    os.path.join(os.path.dirname(__file__), "..", "..", "UC-083", "code"),
]

for _path in _paths:
    _abs = os.path.abspath(_path)
    if _abs not in sys.path and os.path.isdir(_abs):
        sys.path.insert(0, _abs)
