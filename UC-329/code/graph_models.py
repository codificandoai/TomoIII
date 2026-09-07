"""
UC-329 — Modelos de datos para GraphRAG-GoT.

Define las estructuras del grafo de conocimiento, nodos del pensamiento,
caminos de razonamiento, métricas y resultados.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
import time
import uuid


class NodeType(Enum):
    """Tipos de nodo en el grafo de conocimiento."""
    ENTITY = "entity"
    CONCEPT = "concept"
    DOCUMENT = "document"
    CHUNK = "chunk"
    HYPOTHESIS = "hypothesis"
    EVIDENCE = "evidence"
    CONCLUSION = "conclusion"


class EdgeType(Enum):
    """Tipos de relación entre nodos."""
    CAUSES = "causes"
    PART_OF = "part_of"
    IS_A = "is_a"
    SIMILAR_TO = "similar_to"
    CONTRADICTS = "contradicts"
    SUPPORTS = "supports"
    REFUTES = "refutes"
    BEFORE = "before"
    AFTER = "after"
    RELATED_TO = "related_to"


class ReasoningType(Enum):
    """Tipos de razonamiento identificados en un camino."""
    CAUSAL = "causal"
    COMPARATIVE = "comparative"
    HIERARCHICAL = "hierarchical"
    TEMPORAL = "temporal"
    ASSOCIATIVE = "associative"


class ThoughtRole(Enum):
    """Roles de un nodo dentro del grafo del pensamiento."""
    PREMISE = "premise"
    EVIDENCE = "evidence"
    INFERENCE = "inference"
    CONCLUSION = "conclusion"
    COUNTEREXAMPLE = "counterexample"
    HYPOTHESIS = "hypothesis"
    UNCERTAINTY = "uncertainty"


@dataclass
class GraphNode:
    """Nodo de un grafo de conocimiento o pensamiento."""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    label: str = ""
    node_type: NodeType = NodeType.ENTITY
    embedding: List[float] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    source_id: Optional[str] = None
    confidence: float = 0.7
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "node_type": self.node_type.value,
            "attributes": self.attributes,
            "source_id": self.source_id,
            "confidence": round(self.confidence, 4),
            "timestamp": self.timestamp,
        }


@dataclass
class GraphEdge:
    """Arista entre nodos del grafo."""
    edge_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    source: str = ""
    target: str = ""
    edge_type: EdgeType = EdgeType.RELATED_TO
    weight: float = 1.0
    semantic_weight: float = 0.0
    temporal_weight: float = 0.0
    authority_weight: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)
    source_id: Optional[str] = None

    @property
    def composite_weight(self) -> float:
        """Peso combinado de la arista."""
        return self.weight + self.semantic_weight + self.temporal_weight + self.authority_weight

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type.value,
            "weight": round(self.weight, 4),
            "semantic_weight": round(self.semantic_weight, 4),
            "temporal_weight": round(self.temporal_weight, 4),
            "authority_weight": round(self.authority_weight, 4),
            "composite_weight": round(self.composite_weight, 4),
            "attributes": self.attributes,
            "source_id": self.source_id,
        }


@dataclass
class ReasoningPath:
    """Camino de razonamiento sobre el grafo."""
    path_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    nodes: List[str] = field(default_factory=list)
    edges: List[str] = field(default_factory=list)
    score: float = 0.0
    reasoning_type: ReasoningType = ReasoningType.ASSOCIATIVE
    diversity_score: float = 0.0
    support_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path_id": self.path_id,
            "nodes": self.nodes,
            "edges": self.edges,
            "score": round(self.score, 4),
            "reasoning_type": self.reasoning_type.value,
            "diversity_score": round(self.diversity_score, 4),
            "support_count": self.support_count,
            "length": len(self.nodes),
        }


@dataclass
class ThoughtNode:
    """Nodo dentro del Grafo del Pensamiento (GoT)."""
    thought_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    label: str = ""
    role: ThoughtRole = ThoughtRole.HYPOTHESIS
    node_refs: List[str] = field(default_factory=list)
    abstraction_level: int = 1  # 1: concreto, 4: meta
    community_id: Optional[str] = None
    support_score: float = 0.0
    confidence: float = 0.7
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thought_id": self.thought_id,
            "label": self.label,
            "role": self.role.value,
            "node_refs": self.node_refs,
            "abstraction_level": self.abstraction_level,
            "community_id": self.community_id,
            "support_score": round(self.support_score, 4),
            "confidence": round(self.confidence, 4),
            "attributes": self.attributes,
        }


@dataclass
class ThoughtEdge:
    """Arista entre nodos del pensamiento."""
    thought_edge_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    source: str = ""
    target: str = ""
    edge_type: EdgeType = EdgeType.SUPPORTS
    weight: float = 1.0
    justification: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thought_edge_id": self.thought_edge_id,
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type.value,
            "weight": round(self.weight, 4),
            "justification": self.justification,
        }


@dataclass
class GraphMetrics:
    """Métricas de razonamiento sobre un grafo."""
    node_count: int = 0
    edge_count: int = 0
    density: float = 0.0
    diameter: int = 0
    avg_path_length: float = 0.0
    reasoning_depth: float = 0.0
    diversity: float = 0.0
    consistency: float = 1.0
    exhaustiveness: float = 0.0
    explainability: float = 0.0
    contradiction_count: int = 0
    community_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "density": round(self.density, 4),
            "diameter": self.diameter,
            "avg_path_length": round(self.avg_path_length, 4),
            "reasoning_depth": round(self.reasoning_depth, 4),
            "diversity": round(self.diversity, 4),
            "consistency": round(self.consistency, 4),
            "exhaustiveness": round(self.exhaustiveness, 4),
            "explainability": round(self.explainability, 4),
            "contradiction_count": self.contradiction_count,
            "community_count": self.community_count,
        }


@dataclass
class GraphRAGGoTResult:
    """Resultado final de GraphRAG-GoT."""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query: str = ""
    answer: str = ""
    answer_structured: Dict[str, Any] = field(default_factory=dict)
    knowledge_graph: Dict[str, Any] = field(default_factory=dict)
    thought_graph: Dict[str, Any] = field(default_factory=dict)
    reasoning_paths: List[ReasoningPath] = field(default_factory=list)
    contradictions: List[Dict[str, Any]] = field(default_factory=list)
    metrics: GraphMetrics = field(default_factory=GraphMetrics)
    narrative: str = ""
    visualization_data: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    uncertainties: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "query": self.query,
            "answer": self.answer,
            "answer_structured": self.answer_structured,
            "knowledge_graph": self.knowledge_graph,
            "thought_graph": self.thought_graph,
            "reasoning_paths": [p.to_dict() for p in self.reasoning_paths],
            "contradictions": self.contradictions,
            "metrics": self.metrics.to_dict(),
            "narrative": self.narrative,
            "visualization_data": self.visualization_data,
            "recommendations": self.recommendations,
            "uncertainties": self.uncertainties,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp,
        }


@dataclass
class GraphRAGGoTConfig:
    """Configuración del motor GraphRAG-GoT."""
    max_search_depth: int = 4
    relevance_threshold: float = 0.5
    top_k_paths: int = 5
    context_window: int = 3
    pruning_factor: float = 0.3
    min_path_score: float = 0.1
    min_consistency: float = 0.8
    min_diversity: float = 0.5
    enable_counterfactual: bool = False
    cache_paths: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_search_depth": self.max_search_depth,
            "relevance_threshold": self.relevance_threshold,
            "top_k_paths": self.top_k_paths,
            "context_window": self.context_window,
            "pruning_factor": self.pruning_factor,
            "min_path_score": self.min_path_score,
            "min_consistency": self.min_consistency,
            "min_diversity": self.min_diversity,
            "enable_counterfactual": self.enable_counterfactual,
            "cache_paths": self.cache_paths,
        }
