"""
UC-329 — Wrapper de importación para módulos con guión en el nombre.

Permite: from uc329 import UCGraphRAGGoTLayer
"""

import importlib

_mod = importlib.import_module("UC-329")

UCGraphRAGGoTLayer = _mod.UCGraphRAGGoTLayer
demo = _mod.demo

from orchestrator_329 import GraphRAGGoTEngine  # noqa: E402, F401
from graph_models import (  # noqa: E402, F401
    GraphRAGGoTConfig,
    GraphRAGGoTResult,
    GraphNode,
    GraphEdge,
    ThoughtNode,
    ThoughtEdge,
    ReasoningPath,
    GraphMetrics,
    NodeType,
    EdgeType,
    ReasoningType,
    ThoughtRole,
)
from entity_extractor import EntityExtractor  # noqa: E402, F401
from relation_extractor import RelationExtractor  # noqa: E402, F401
from knowledge_graph import KnowledgeGraph  # noqa: E402, F401
from graph_memory import GraphMemory  # noqa: E402, F401
from graph_rag_retriever import GraphRAGRetriever  # noqa: E402, F401
from graph_of_thoughts import GraphOfThoughts  # noqa: E402, F401
from path_ranker import PathRanker  # noqa: E402, F401
from contradiction_detector import ContradictionDetector  # noqa: E402, F401
from graph_plasticity import GraphPlasticity  # noqa: E402, F401
from meta_reasoning import MetaReasoning  # noqa: E402, F401
from observability_329 import ObservabilityManager  # noqa: E402, F401

__all__ = [
    "UCGraphRAGGoTLayer",
    "GraphRAGGoTEngine",
    "demo",
    "GraphRAGGoTConfig",
    "GraphRAGGoTResult",
    "GraphNode",
    "GraphEdge",
    "ThoughtNode",
    "ThoughtEdge",
    "ReasoningPath",
    "GraphMetrics",
    "NodeType",
    "EdgeType",
    "ReasoningType",
    "ThoughtRole",
    "EntityExtractor",
    "RelationExtractor",
    "KnowledgeGraph",
    "GraphMemory",
    "GraphRAGRetriever",
    "GraphOfThoughts",
    "PathRanker",
    "ContradictionDetector",
    "GraphPlasticity",
    "MetaReasoning",
    "ObservabilityManager",
]
