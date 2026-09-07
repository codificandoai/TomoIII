"""
UC-087 — Wrapper de importación para módulos con guión en el nombre.

Permite: from uc087 import UCMLSecOpsLayer
"""

import importlib

_mod = importlib.import_module("UC-087")

UCMLSecOpsLayer = _mod.UCMLSecOpsLayer
demo = _mod.demo

from model_guardian import ModelSecurityGuardian  # noqa: E402, F401
from models_087 import (  # noqa: E402, F401
    MLSecOpsConfig,
    DataPoint,
    SecurityDecision,
    DefenseAction,
    ModelPromotion,
    ThreatCategory,
    ValidationReport,
    RobustnessReport,
    TriggerReport,
    ModelVersion,
    MLSecOpsResult,
)
from data_signing import DataSigning  # noqa: E402, F401
from provenance_validator import ProvenanceValidator  # noqa: E402, F401
from input_filter import InputFilter  # noqa: E402, F401
from adversarial_generator import AdversarialGenerator  # noqa: E402, F401
from sandbox_model import SandboxLogisticModel  # noqa: E402, F401
from sandbox_trainer import SandboxTrainer  # noqa: E402, F401
from robustness_evaluator import RobustnessEvaluator  # noqa: E402, F401
from trigger_detector import TriggerDetector  # noqa: E402, F401
from rollback_manager import RollbackManager  # noqa: E402, F401
from alert_manager_087 import AlertManager087  # noqa: E402, F401
from observability_087 import ObservabilityManager  # noqa: E402, F401

__all__ = [
    "UCMLSecOpsLayer",
    "ModelSecurityGuardian",
    "demo",
    "MLSecOpsConfig",
    "DataPoint",
    "SecurityDecision",
    "DefenseAction",
    "ModelPromotion",
    "ThreatCategory",
    "ValidationReport",
    "RobustnessReport",
    "TriggerReport",
    "ModelVersion",
    "MLSecOpsResult",
    "DataSigning",
    "ProvenanceValidator",
    "InputFilter",
    "AdversarialGenerator",
    "SandboxLogisticModel",
    "SandboxTrainer",
    "RobustnessEvaluator",
    "TriggerDetector",
    "RollbackManager",
    "AlertManager087",
    "ObservabilityManager",
]
