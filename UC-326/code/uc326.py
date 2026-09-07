"""
UC-326 — Wrapper de importación para módulos con guión en el nombre.

Permite: from uc326 import UCMaqriLayer
en lugar de importar directamente el módulo con guión.
"""

import importlib

_mod = importlib.import_module("UC-326")

UCMaqriLayer = _mod.UCMaqriLayer
demo = _mod.demo
default_kb = _mod.default_kb

from maqri_engine import MaqriEngine  # noqa: E402, F401
from maqri_models import (  # noqa: E402, F401
    MaqriConfig,
    MaqriResult,
    MaqriIteration,
    SearchEpisode,
    RetrievedDocument,
    QueryVariant,
    ProceduralRule,
    CriticAssessment,
    WorkingMemory,
    MemoryQuery,
    MemoryType,
    QueryStrategy,
    RetrievalVerdict,
)
from episodic_memory import EpisodicMemory  # noqa: E402, F401
from semantic_memory import SemanticMemory  # noqa: E402, F401
from procedural_memory import ProceduralMemory  # noqa: E402, F401
from query_refiner_326 import QueryRefiner326  # noqa: E402, F401
from divergence_strategy import DivergenceStrategy  # noqa: E402, F401
from critic_evaluator import CriticEvaluator  # noqa: E402, F401
from cross_retriever import CrossRetriever  # noqa: E402, F401
from observability_326 import ObservabilityManager  # noqa: E402, F401

__all__ = [
    "UCMaqriLayer",
    "MaqriEngine",
    "MaqriConfig",
    "MaqriResult",
    "MaqriIteration",
    "SearchEpisode",
    "RetrievedDocument",
    "QueryVariant",
    "ProceduralRule",
    "CriticAssessment",
    "WorkingMemory",
    "MemoryQuery",
    "MemoryType",
    "QueryStrategy",
    "RetrievalVerdict",
    "EpisodicMemory",
    "SemanticMemory",
    "ProceduralMemory",
    "QueryRefiner326",
    "DivergenceStrategy",
    "CriticEvaluator",
    "CrossRetriever",
    "ObservabilityManager",
]
