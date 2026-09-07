"""
UC-326 — Modelos de datos para MAQRI (Memory-Augmented Query Refinement Iterative).

Define las estructuras compartidas por el sistema de memoria y búsqueda
inteligente del agente. MAQRI sirve como capa de retrieval para UC-325,
proporcionando:
- Memoria episódica (experiencias pasadas de búsqueda).
- Memoria semántica (base de conocimiento del dominio).
- Memoria procedimental (reglas heurísticas de búsqueda).
- Refinamiento iterativo de queries con divergencia forzada.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any
import time
import uuid
import hashlib


# ─── ENUMS ───────────────────────────────────────────────────────────────────

class MemoryType(Enum):
    """Tipos de memoria soportados por MAQRI."""
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    EXTERNAL = "external"


class QueryStrategy(Enum):
    """Estrategias de refinamiento de query."""
    EXPAND = "expand"
    SPECIALIZE = "specialize"
    DIVERGE = "diverge"
    CONTEXTUALIZE = "contextualize"
    ABSTRACT = "abstract"


class RetrievalVerdict(Enum):
    """Veredictos del proceso de retrieval."""
    CONVERGED = "converged"
    MAX_ITERATIONS = "max_iterations"
    INSUFFICIENT_DATA = "insufficient_data"
    REDUNDANT_QUERY = "redundant_query"
    DIVERGED = "diverged"


# ─── DATACLASSES ─────────────────────────────────────────────────────────────

@dataclass
class RetrievedDocument:
    """Documento recuperado por MAQRI."""
    doc_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    content: str = ""
    source: str = ""
    memory_type: MemoryType = MemoryType.SEMANTIC
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    retrieval_round: int = 1
    fingerprint: str = ""

    def __post_init__(self):
        if not self.fingerprint and self.content:
            normalized = " ".join(self.content.lower().split())
            self.fingerprint = hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "content": self.content[:250],
            "source": self.source,
            "memory_type": self.memory_type.value,
            "score": round(self.score, 4),
            "metadata": self.metadata,
            "retrieval_round": self.retrieval_round,
            "fingerprint": self.fingerprint,
        }


@dataclass
class SearchEpisode:
    """Episodio de búsqueda guardado en memoria episódica."""
    episode_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    original_query: str = ""
    refined_query: str = ""
    retrieved_docs: List[RetrievedDocument] = field(default_factory=list)
    relevance_score: float = 0.0
    missing_info: str = ""
    failure_reason: str = ""
    iteration: int = 0
    timestamp: float = field(default_factory=time.time)

    @property
    def success(self) -> bool:
        return not bool(self.failure_reason)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "original_query": self.original_query,
            "refined_query": self.refined_query,
            "relevance_score": round(self.relevance_score, 4),
            "missing_info": self.missing_info,
            "failure_reason": self.failure_reason,
            "iteration": self.iteration,
            "num_docs": len(self.retrieved_docs),
            "success": self.success,
            "timestamp": self.timestamp,
        }


@dataclass
class QueryVariant:
    """Variante de una query refinada."""
    query: str = ""
    strategy: QueryStrategy = QueryStrategy.EXPAND
    source_query: str = ""
    expected_focus: str = ""
    estimated_quality: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "strategy": self.strategy.value,
            "source_query": self.source_query,
            "expected_focus": self.expected_focus,
            "estimated_quality": round(self.estimated_quality, 4),
        }


@dataclass
class ProceduralRule:
    """Regla heurística de memoria procedimental."""
    rule_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str = ""
    condition: str = ""
    action: str = ""
    priority: float = 0.5
    hits: int = 0
    successes: int = 0

    @property
    def success_rate(self) -> float:
        return self.successes / self.hits if self.hits > 0 else 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "condition": self.condition,
            "action": self.action,
            "priority": round(self.priority, 4),
            "hits": self.hits,
            "successes": self.successes,
            "success_rate": round(self.success_rate, 4),
        }


@dataclass
class CriticAssessment:
    """Evaluación del módulo Critic sobre un retrieval."""
    relevance_score: float = 0.0
    coverage_score: float = 0.0
    novelty_score: float = 0.0
    missing_info: str = ""
    failure_reason: str = ""
    confidence: float = 0.0

    @property
    def overall_score(self) -> float:
        return (self.relevance_score * 0.4
                + self.coverage_score * 0.35
                + self.novelty_score * 0.25)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relevance_score": round(self.relevance_score, 4),
            "coverage_score": round(self.coverage_score, 4),
            "novelty_score": round(self.novelty_score, 4),
            "overall_score": round(self.overall_score, 4),
            "missing_info": self.missing_info,
            "failure_reason": self.failure_reason,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class WorkingMemory:
    """Memoria de trabajo de corto plazo para una sesión MAQRI."""
    original_goal: str = ""
    accumulated_facts: List[str] = field(default_factory=list)
    failed_approaches: List[str] = field(default_factory=list)
    active_hypotheses: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_goal": self.original_goal,
            "accumulated_facts": self.accumulated_facts[:20],
            "failed_approaches": self.failed_approaches,
            "active_hypotheses": self.active_hypotheses,
        }


@dataclass
class MaqriConfig:
    """Configuración del motor MAQRI."""
    max_iterations: int = 5
    redundancy_threshold: float = 0.8
    convergence_threshold: float = 0.85
    min_relevance_threshold: float = 0.15
    top_k_per_source: int = 5
    max_variants: int = 5
    enable_divergence: bool = True
    enable_episodic_memory: bool = True
    enable_procedural_rules: bool = True
    similarity_window: int = 5


@dataclass
class MaqriIteration:
    """Resultado de una iteración MAQRI."""
    iteration: int = 0
    query: str = ""
    variants_used: List[str] = field(default_factory=list)
    docs_retrieved: int = 0
    docs_unique: int = 0
    assessment: Optional[CriticAssessment] = None
    divergence_applied: bool = False
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "query": self.query,
            "variants_used": self.variants_used,
            "docs_retrieved": self.docs_retrieved,
            "docs_unique": self.docs_unique,
            "assessment": self.assessment.to_dict() if self.assessment else None,
            "divergence_applied": self.divergence_applied,
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class MaqriResult:
    """Resultado final de una búsqueda MAQRI."""
    query: str = ""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    final_query: str = ""
    docs: List[RetrievedDocument] = field(default_factory=list)
    episodes: List[SearchEpisode] = field(default_factory=list)
    iterations: List[MaqriIteration] = field(default_factory=list)
    working_memory: WorkingMemory = field(default_factory=WorkingMemory)
    verdict: RetrievalVerdict = RetrievalVerdict.INSUFFICIENT_DATA
    iterations_executed: int = 0
    final_score: float = 0.0
    duration_ms: float = 0.0
    success: bool = False

    @property
    def unique_facts(self) -> List[str]:
        """Retorna hechos únicos acumulados."""
        seen = set()
        unique = []
        for fact in self.working_memory.accumulated_facts:
            key = " ".join(fact.lower().split())
            if key not in seen:
                seen.add(key)
                unique.append(fact)
        return unique

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "trace_id": self.trace_id,
            "final_query": self.final_query,
            "verdict": self.verdict.value,
            "success": self.success,
            "iterations_executed": self.iterations_executed,
            "final_score": round(self.final_score, 4),
            "total_docs": len(self.docs),
            "unique_facts": len(self.unique_facts),
            "duration_ms": round(self.duration_ms, 2),
            "docs": [d.to_dict() for d in self.docs[:20]],
            "iterations": [it.to_dict() for it in self.iterations],
            "episodes": [e.to_dict() for e in self.episodes],
            "working_memory": self.working_memory.to_dict(),
        }


@dataclass
class MemoryQuery:
    """Query estructurada para múltiples stores de memoria."""
    query: str = ""
    domain: str = "general"
    context: str = ""
    iteration: int = 0
    exclude_recent: List[str] = field(default_factory=list)
    preferred_sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "domain": self.domain,
            "context": self.context,
            "iteration": self.iteration,
            "exclude_recent": self.exclude_recent,
            "preferred_sources": self.preferred_sources,
        }
