"""
UC-162 — Wrapper de importación para compatibilidad con guión en nombre.
"""

import importlib
import sys
import os

# Importar UC-162.py (guión en nombre requiere importlib)
_module_path = os.path.join(os.path.dirname(__file__), "UC-162.py")
_spec = importlib.util.spec_from_file_location("UC_162_internal", _module_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

UCLLMOpsLayer = _mod.UCLLMOpsLayer
run_demo = _mod.run_demo

from llmops_guardian import LLMOpsGuardian  # noqa: F401,E402
from models_162 import (  # noqa: F401,E402
    LLMOpsConfig,
    CorpusDocument,
    DocumentMetadata,
)
