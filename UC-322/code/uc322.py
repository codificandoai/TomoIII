"""Wrapper module para importar UC-322.py (que tiene guión en el nombre).

Permite importar como `from uc322 import ConflictResolutionLayer`.
"""
import importlib.util
import os

_spec = importlib.util.spec_from_file_location(
    "UC_322_internal",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "UC-322.py"),
)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

# Re-exportar todo
ConflictResolutionLayer = _module.ConflictResolutionLayer
demo = _module.demo

# Re-exportar submódulos para conveniencia
from conflict_models import *  # noqa: F401, F403
from reputation_system import ReputationSystem  # noqa: F401
from negotiation_engine import NegotiationEngine  # noqa: F401
from voting_system import VotingSystem  # noqa: F401
from cnp_dynamic import DynamicCNP  # noqa: F401
from escalation_protocol import EscalationProtocol  # noqa: F401
from duplicate_detection import DuplicateDetection, DeadlockDetector  # noqa: F401
from observability import ObservabilityManager  # noqa: F401
