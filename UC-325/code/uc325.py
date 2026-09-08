"""
UC-325 — Wrapper de importación para módulos con guión en el nombre.

Permite: from uc325 import ReasoningLoopEngine
en lugar de: from importlib import import_module; mod = import_module("UC-325")
"""

import importlib

_mod = importlib.import_module("UC-325")

ReasoningLoopEngine = _mod.ReasoningLoopEngine
StubRetriever = _mod.StubRetriever
StubHypothesisGenerator = _mod.StubHypothesisGenerator
demo = _mod.demo

from reasoning_models import (  # noqa: E402, F401
    ReasoningState,
    ReasoningResult,
    ReasoningConfig,
    ReasoningVerdict,
    RetrievedChunk,
    Hypothesis,
    KnowledgeGap,
    QualityScore,
    HallucinationReport,
    LoopIteration,
    LoopPhase,
    HypothesisStatus,
    DEFAULT_QUALITY_THRESHOLDS,
)

from quality_gates import QualityGateEvaluator  # noqa: E402, F401
from hallucination_detector import HallucinationDetector  # noqa: E402, F401
from query_refiner import QueryRefiner  # noqa: E402, F401
from retrieval_evaluator import RetrievalEvaluator  # noqa: E402, F401
from convergence_monitor import ConvergenceMonitor  # noqa: E402, F401
from meta_reasoning_orchestrator import (  # noqa: E402, F401
    MetaReasoningOrchestrator,
    ReasoningHeuristic,
    HeuristicProfile,
    MetaReasoningPlan,
)
from observability_325 import ObservabilityManager  # noqa: E402, F401

__all__ = [
    "ReasoningLoopEngine",
    "StubRetriever",
    "StubHypothesisGenerator",
    "ReasoningState",
    "ReasoningResult",
    "ReasoningConfig",
    "ReasoningVerdict",
    "RetrievedChunk",
    "Hypothesis",
    "KnowledgeGap",
    "QualityScore",
    "HallucinationReport",
    "LoopIteration",
    "LoopPhase",
    "HypothesisStatus",
    "QualityGateEvaluator",
    "HallucinationDetector",
    "QueryRefiner",
    "RetrievalEvaluator",
    "ConvergenceMonitor",
    "MetaReasoningOrchestrator",
    "ReasoningHeuristic",
    "HeuristicProfile",
    "MetaReasoningPlan",
    "ObservabilityManager",
]
