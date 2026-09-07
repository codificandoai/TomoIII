"""Helper para importar el cerebro AGI desde UC-315 sin copiar archivos.

UC-322 es una capa de resolución de conflictos que envuelve al cerebro AGI
(UC-315) sin modificarlo. Este módulo agrega UC-315/code al sys.path para
que los módulos de UC-322 puedan importar componentes del cerebro cuando
sea necesario (escalación, integración con GeneralOrchestrator, etc.).

En producción, usar PYTHONPATH=../../UC-315/code como alternativa.
"""
import os
import sys

_UC315_CODE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "UC-315", "code")
)

if _UC315_CODE not in sys.path:
    sys.path.insert(0, _UC315_CODE)
