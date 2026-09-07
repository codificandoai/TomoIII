"""
UC-330 — Wrapper de importación para módulos con guión en el nombre.

Permite: from uc330 import UCBalanceExLayer
"""

import importlib

_mod = importlib.import_module("UC-330")

UCBalanceExLayer = _mod.UCBalanceExLayer
demo = _mod.demo

from balance_ex_engine import BalanceExEngine  # noqa: E402, F401
from balance_ex_models import (  # noqa: E402, F401
    BalanceExConfig,
    BalanceExResult,
    BalanceMetrics,
    ContextSnapshot,
    ActionRecord,
    Decision,
    DecisionMode,
    ExplorationStrategy,
)
from environment_detector import EnvironmentDetector  # noqa: E402, F401
from context_bandit import ContextualBandit  # noqa: E402, F401
from q_learning_table import QLearningTable  # noqa: E402, F401
from curiosity_engine import CuriosityEngine  # noqa: E402, F401
from exploration_budget import ExplorationBudget  # noqa: E402, F401
from policy_selector import PolicySelector  # noqa: E402, F401
from safety_governor import SafetyGovernor  # noqa: E402, F401
from observability_330 import ObservabilityManager  # noqa: E402, F401

__all__ = [
    "UCBalanceExLayer",
    "BalanceExEngine",
    "demo",
    "BalanceExConfig",
    "BalanceExResult",
    "BalanceMetrics",
    "ContextSnapshot",
    "ActionRecord",
    "Decision",
    "DecisionMode",
    "ExplorationStrategy",
    "EnvironmentDetector",
    "ContextualBandit",
    "QLearningTable",
    "CuriosityEngine",
    "ExplorationBudget",
    "PolicySelector",
    "SafetyGovernor",
    "ObservabilityManager",
]
