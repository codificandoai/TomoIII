"""
UC-325 — Modelos de datos para el Motor de Bucles de Razonamiento Autorreflexivos.

Define los dataclasses, enums y estructuras compartidas por todos los módulos
del sistema de razonamiento iterativo. Cada iteración del bucle produce y consume
estas estructuras para mantener estado, evaluar calidad y converger.
"""

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import List, Dict, Optional, Any
import time
import uuid
import hashlib
import math


# ─── ENUMS ───────────────────────────────────────────────────────────────────

class LoopPhase(Enum):
    """Fases del bucle de razonamiento."""
    DISCOVER = "discover"
    REFINE = "refine"
    SYNTHESIZE = "synthesize"
    CONVERGE = "converge"


class QualityDimension(Enum):
    """Dimensiones de calidad evaluadas en cada iteración."""
    RELEVANCE = "relevance"
    COVERAGE = "coverage"
    CONSISTENCY = "consistency"
    CONFIDENCE = "confidence"
    NOVELTY = "novelty"


class HypothesisStatus(Enum):
    """Estado de una hipótesis en el ciclo de razonamiento."""
    ACTIVE = "active"
    REFUTED = "refuted"
    CONFIRMED = "confirmed"
    MERGED = "merged"


class ReasoningVerdict(Enum):
    """Veredicto del bucle de razonamiento."""
    CONVERGED = "converged"
    MAX_ROUNDS = "max_rounds"
    STALLED = "stalled"
    INSUFFICIENT_DATA = "insufficient_data"
    HALLUCINATION_DETECTED = "hallucination_detected"


# ─── DATACLASSES ─────────────────────────────────────────────────────────────

@dataclass
class RetrievedChunk:
    """Fragmento de información recuperado por el sistema de retrieval."""
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    content: str = ""
    source: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    retrieval_round: int = 1
    used_in_hypothesis: bool = False
    relevance_score: float = 0.0
    fingerprint: str = ""

    def __post_init__(self):
        if not self.fingerprint and self.content:
            normalized = " ".join(self.content.lower().split())
            self.fingerprint = hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "content": self.content[:200],
            "source": self.source,
            "score": round(self.score, 4),
            "retrieval_round": self.retrieval_round,
            "used_in_hypothesis": self.used_in_hypothesis,
            "relevance_score": round(self.relevance_score, 4),
            "fingerprint": self.fingerprint,
        }


@dataclass
class Hypothesis:
    """Hipótesis generada durante el razonamiento."""
    hypothesis_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    statement: str = ""
    supporting_chunks: List[str] = field(default_factory=list)
    confidence: float = 0.5
    generation_round: int = 1
    status: HypothesisStatus = HypothesisStatus.ACTIVE
    refuted_by: Optional[str] = None
    coherence_score: float = 0.0
    evidence_strength: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "statement": self.statement,
            "supporting_chunks": self.supporting_chunks,
            "confidence": round(self.confidence, 4),
            "generation_round": self.generation_round,
            "status": self.status.value,
            "refuted_by": self.refuted_by,
            "coherence_score": round(self.coherence_score, 4),
            "evidence_strength": round(self.evidence_strength, 4),
        }


@dataclass
class KnowledgeGap:
    """Gap de conocimiento identificado durante el razonamiento."""
    gap_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    description: str = ""
    related_questions: List[str] = field(default_factory=list)
    priority: float = 0.5
    attempts_made: int = 0
    max_attempts: int = 3
    filled: bool = False
    filled_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "description": self.description,
            "related_questions": self.related_questions,
            "priority": round(self.priority, 4),
            "attempts_made": self.attempts_made,
            "filled": self.filled,
            "filled_by": self.filled_by,
        }


@dataclass
class QualityScore:
    """Score de calidad para una iteración del razonamiento."""
    relevance: float = 0.0
    coverage: float = 0.0
    consistency: float = 0.0
    confidence: float = 0.0
    novelty: float = 0.0
    round_number: int = 0
    timestamp: float = field(default_factory=time.time)

    @property
    def overall(self) -> float:
        """Score promedio ponderado de todas las dimensiones."""
        weights = {
            "relevance": 0.25,
            "coverage": 0.20,
            "consistency": 0.25,
            "confidence": 0.20,
            "novelty": 0.10,
        }
        return (
            weights["relevance"] * self.relevance
            + weights["coverage"] * self.coverage
            + weights["consistency"] * self.consistency
            + weights["confidence"] * self.confidence
            + weights["novelty"] * self.novelty
        )

    @property
    def passed(self) -> bool:
        """Indica si pasó todas las quality gates."""
        thresholds = DEFAULT_QUALITY_THRESHOLDS
        return (
            self.relevance >= thresholds["relevance"]
            and self.coverage >= thresholds["coverage"]
            and self.consistency >= thresholds["consistency"]
            and self.confidence >= thresholds["confidence"]
            and self.novelty >= thresholds["novelty"]
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relevance": round(self.relevance, 4),
            "coverage": round(self.coverage, 4),
            "consistency": round(self.consistency, 4),
            "confidence": round(self.confidence, 4),
            "novelty": round(self.novelty, 4),
            "overall": round(self.overall, 4),
            "passed": self.passed,
            "round_number": self.round_number,
        }


@dataclass
class HallucinationReport:
    """Reporte de detección de alucinaciones en una respuesta."""
    detected: bool = False
    hallucination_type: Optional[str] = None
    unsupported_claims: List[str] = field(default_factory=list)
    fabricated_sources: List[str] = field(default_factory=list)
    confidence_inflation: float = 0.0
    severity: float = 0.0
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected": self.detected,
            "hallucination_type": self.hallucination_type,
            "unsupported_claims": self.unsupported_claims,
            "fabricated_sources": self.fabricated_sources,
            "confidence_inflation": round(self.confidence_inflation, 4),
            "severity": round(self.severity, 4),
            "recommendation": self.recommendation,
        }


@dataclass
class LoopIteration:
    """Resultado de una iteración del bucle de razonamiento."""
    round_number: int = 0
    phase: LoopPhase = LoopPhase.DISCOVER
    chunks_added: int = 0
    chunks_total: int = 0
    hypotheses_generated: int = 0
    hypotheses_refuted: int = 0
    hypotheses_active: int = 0
    gaps_identified: int = 0
    gaps_filled: int = 0
    quality: Optional[QualityScore] = None
    hallucination_report: Optional[HallucinationReport] = None
    convergence_delta: float = 0.0
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_number": self.round_number,
            "phase": self.phase.value,
            "chunks_added": self.chunks_added,
            "chunks_total": self.chunks_total,
            "hypotheses_generated": self.hypotheses_generated,
            "hypotheses_refuted": self.hypotheses_refuted,
            "hypotheses_active": self.hypotheses_active,
            "gaps_identified": self.gaps_identified,
            "gaps_filled": self.gaps_filled,
            "quality": self.quality.to_dict() if self.quality else None,
            "hallucination_report": self.hallucination_report.to_dict() if self.hallucination_report else None,
            "convergence_delta": round(self.convergence_delta, 4),
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class ReasoningState:
    """Estado completo y persistente del razonamiento a través de loops."""
    query: str = ""
    domain: str = "general"
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Acumulado a través de loops
    all_chunks: Dict[str, RetrievedChunk] = field(default_factory=dict)
    hypotheses: Dict[str, Hypothesis] = field(default_factory=dict)
    gaps: Dict[str, KnowledgeGap] = field(default_factory=dict)

    # Historial de iteraciones
    iterations: List[LoopIteration] = field(default_factory=list)

    # Métricas de convergencia
    round_number: int = 0
    max_rounds: int = 5
    confidence_trajectory: List[float] = field(default_factory=list)

    # Salida final
    final_answer: Optional[str] = None
    final_confidence: float = 0.0
    verdict: ReasoningVerdict = ReasoningVerdict.INSUFFICIENT_DATA
    citations: List[Dict[str, Any]] = field(default_factory=list)

    # Timing
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    @property
    def active_hypotheses(self) -> List[Hypothesis]:
        return [h for h in self.hypotheses.values() if h.status == HypothesisStatus.ACTIVE]

    @property
    def unfilled_gaps(self) -> List[KnowledgeGap]:
        return [g for g in self.gaps.values() if not g.filled and g.attempts_made < g.max_attempts]

    @property
    def convergence_score(self) -> float:
        if len(self.confidence_trajectory) < 2:
            return 0.0
        return abs(self.confidence_trajectory[-1] - self.confidence_trajectory[-2])

    @property
    def duration_ms(self) -> float:
        end = self.completed_at or time.time()
        return (end - self.started_at) * 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "domain": self.domain,
            "trace_id": self.trace_id,
            "round_number": self.round_number,
            "max_rounds": self.max_rounds,
            "chunks_total": len(self.all_chunks),
            "hypotheses_total": len(self.hypotheses),
            "hypotheses_active": len(self.active_hypotheses),
            "gaps_total": len(self.gaps),
            "gaps_unfilled": len(self.unfilled_gaps),
            "confidence_trajectory": [round(c, 4) for c in self.confidence_trajectory],
            "convergence_score": round(self.convergence_score, 4),
            "final_answer": self.final_answer,
            "final_confidence": round(self.final_confidence, 4),
            "verdict": self.verdict.value,
            "citations": self.citations,
            "iterations": [it.to_dict() for it in self.iterations],
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class ReasoningResult:
    """Resultado final completo del proceso de razonamiento."""
    query: str = ""
    domain: str = "general"
    trace_id: str = ""
    answer: Optional[str] = None
    confidence: float = 0.0
    verdict: ReasoningVerdict = ReasoningVerdict.INSUFFICIENT_DATA
    rounds_executed: int = 0
    citations: List[Dict[str, Any]] = field(default_factory=list)
    quality_scores: List[Dict[str, Any]] = field(default_factory=list)
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    gaps_remaining: List[Dict[str, Any]] = field(default_factory=list)
    hallucination_reports: List[Dict[str, Any]] = field(default_factory=list)
    convergence_trajectory: List[float] = field(default_factory=list)
    total_chunks_retrieved: int = 0
    duration_ms: float = 0.0
    success: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "domain": self.domain,
            "trace_id": self.trace_id,
            "answer": self.answer,
            "confidence": round(self.confidence, 4),
            "verdict": self.verdict.value,
            "success": self.success,
            "rounds_executed": self.rounds_executed,
            "citations": self.citations,
            "quality_scores": self.quality_scores,
            "hypotheses": self.hypotheses,
            "gaps_remaining": self.gaps_remaining,
            "hallucination_reports": self.hallucination_reports,
            "convergence_trajectory": [round(c, 4) for c in self.convergence_trajectory],
            "total_chunks_retrieved": self.total_chunks_retrieved,
            "duration_ms": round(self.duration_ms, 2),
        }


# ─── CONFIGURACIÓN ───────────────────────────────────────────────────────────

@dataclass
class ReasoningConfig:
    """Configuración del motor de bucles de razonamiento."""
    max_rounds: int = 5
    min_convergence_delta: float = 0.02
    stall_threshold: int = 2
    max_chunks_per_round: int = 10
    max_hypotheses: int = 20
    chunk_dedup_threshold: float = 0.85
    min_chunk_score: float = 0.3
    hallucination_threshold: float = 0.5
    quality_thresholds: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_QUALITY_THRESHOLDS))
    evidence_weight: float = 0.4
    coherence_weight: float = 0.3
    confidence_weight: float = 0.3


@dataclass
class QueryRefinementConfig:
    """Configuración del refinamiento de queries."""
    max_expansions: int = 5
    synonym_weight: float = 0.3
    specialization_weight: float = 0.4
    generalization_weight: float = 0.3


# ─── CONSTANTES ──────────────────────────────────────────────────────────────

DEFAULT_QUALITY_THRESHOLDS: Dict[str, float] = {
    "relevance": 0.70,
    "coverage": 0.60,
    "consistency": 0.80,
    "confidence": 0.75,
    "novelty": 0.30,
}

QUALITY_WEIGHTS: Dict[str, float] = {
    "relevance": 0.25,
    "coverage": 0.20,
    "consistency": 0.25,
    "confidence": 0.20,
    "novelty": 0.10,
}

HALLUCINATION_PATTERNS: List[str] = [
    "claim_without_evidence",
    "fabricated_source",
    "confidence_inflation",
    "contradiction_with_evidence",
    "extrapolation_beyond_data",
    "temporal_inconsistency",
]
