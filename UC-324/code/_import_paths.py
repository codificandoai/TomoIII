"""Helper para importar el cerebro AGI desde UC-315 sin copiar archivos."""
import os
import sys

_UC315_CODE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "UC-315", "code")
)

if _UC315_CODE not in sys.path:
    sys.path.insert(0, _UC315_CODE)
