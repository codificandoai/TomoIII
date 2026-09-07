"""
UC-328 — Modelos de datos para ORQUESTA-R.

Define las estructuras compartidas por el orquestador resiliente de RAG
empresarial: fuentes de datos, subconsultas, resultados parciales, contexto
persistente, métricas, presupuestos y resultados finales.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any, Callable
import time
import uuid
import hashlib


# ─── ENUMS ───────────────────────────────────────────────────────────────────

class SourceType(Enum):
    """Tipos de fuente de datos externa."""
    API = "api"
    DATABASE = "database"
    VECTOR_STORE = "vector_store"
    DOCUMENT_STORE = "document_store"
    CACHE = "cache"
    INFERENCE = "inference"


class SubqueryStatus(Enum):
    """Estado de una subconsulta."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"
    CACHE_HIT = "cache_hit"


class ExecutionVerdict(Enum):
    """Veredicto final de la ejecución ORQUESTA-R."""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    BUDGET_EXCEEDED = "budget_exceeded"
    LATENCY_EXCEEDED = "latency_exceeded"
    FALLBACK_USED = "fallback_used"
    FAILED = "failed"


class PrivacyPolicy(Enum):
    """Políticas de privacidad soportadas."""
    GDPR = "GDPR"
    HIPAA = "HIPAA"
    CCPA = "CCPA"
    NONE = "NONE"


# ─── DATACLASSES ─────────────────────────────────────────────────────────────

@dataclass
class Source:
    """Fuente de datos externa registrada."""
    source_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str = ""
    source_type: SourceType = SourceType.API
    endpoint: str = ""
    cost_per_call: float = 0.0
    cost_per_kb: float = 0.0
    base_latency_ms: float = 200.0
    reliability: float = 0.9
    rate_limit: int = 10
    schema: Optional[Dict[str, Any]] = None
    capabilities: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "source_type": self.source_type.value,
            "cost_per_call": self.cost_per_call,
            "cost_per_kb": self.cost_per_kb,
            "base_latency_ms": self.base_latency_ms,
            "reliability": self.reliability,
            "rate_limit": self.rate_limit,
            "capabilities": self.capabilities,
            "tags": self.tags,
            "enabled": self.enabled,
        }


@dataclass
class Subquery:
    """Subconsulta atómica generada a partir de una consulta."""
    subquery_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    parent_trace_id: str = ""
    text: str = ""
    priority: float = 0.5
    dependencies: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    status: SubqueryStatus = SubqueryStatus.PENDING
    result: Optional[Any] = None
    source_id: Optional[str] = None
    cost: float = 0.0
    latency_ms: float = 0.0
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subquery_id": self.subquery_id,
            "text": self.text,
            "priority": round(self.priority, 4),
            "dependencies": self.dependencies,
            "required_capabilities": self.required_capabilities,
            "status": self.status.value,
            "source_id": self.source_id,
            "cost": round(self.cost, 6),
            "latency_ms": round(self.latency_ms, 2),
            "confidence": round(self.confidence, 4),
            "metadata": self.metadata,
        }


@dataclass
class PartialResult:
    """Resultado parcial de una fuente para una subconsulta."""
    partial_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    subquery_id: str = ""
    source_id: str = ""
    data: Any = None
    raw_score: float = 0.0
    normalized_score: float = 0.0
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)
    method: str = "direct"  # direct, cached, inferred, fallback
    lineage: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "partial_id": self.partial_id,
            "subquery_id": self.subquery_id,
            "source_id": self.source_id,
            "data": self.data,
            "raw_score": round(self.raw_score, 4),
            "normalized_score": round(self.normalized_score, 4),
            "confidence": round(self.confidence, 4),
            "method": self.method,
            "timestamp": self.timestamp,
            "lineage": self.lineage,
        }


@dataclass
class ResolvedFact:
    """Hecho resuelto tras fusión y resolución de conflictos."""
    key: str = ""
    value: Any = None
    confidence: float = 0.0
    mode: str = "consistent"
    sources: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "confidence": round(self.confidence, 4),
            "mode": self.mode,
            "sources": self.sources,
            "warnings": self.warnings,
        }


@dataclass
class Budget:
    """Presupuesto de ejecución."""
    max_cost: float = 10.0
    max_latency_ms: float = 5000.0
    max_concurrent_calls: int = 10
    max_retries: int = 2
    currency: str = "USD"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_cost": self.max_cost,
            "max_latency_ms": self.max_latency_ms,
            "max_concurrent_calls": self.max_concurrent_calls,
            "max_retries": self.max_retries,
            "currency": self.currency,
        }


@dataclass
class OrquestaConfig:
    """Configuración del orquestador."""
    budget: Budget = field(default_factory=Budget)
    cache_ttl_seconds: int = 300
    cache_enabled: bool = True
    privacy_policies: List[PrivacyPolicy] = field(default_factory=list)
    min_confidence: float = 0.6
    conflict_variance_threshold: float = 0.3
    context_window_size: int = 1000
    default_redundancy: int = 1
    enable_load_balancing: bool = True
    enable_privacy_filter: bool = True


@dataclass
class CacheEntry:
    """Entrada de caché."""
    key: str = ""
    value: Any = None
    created_at: float = field(default_factory=time.time)
    ttl_seconds: int = 300
    access_count: int = 0
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "is_expired": self.is_expired,
            "created_at": self.created_at,
            "ttl_seconds": self.ttl_seconds,
            "access_count": self.access_count,
            "hit_count": self.hit_count,
        }


@dataclass
class ContextVersion:
    """Versión del contexto persistente."""
    version_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    parent_version_id: Optional[str] = None
    delta: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "parent_version_id": self.parent_version_id,
            "timestamp": self.timestamp,
            "dependencies": self.dependencies,
            "delta_keys": list(self.delta.keys()),
        }


@dataclass
class ExecutionMetrics:
    """Métricas de ejecución."""
    total_cost: float = 0.0
    total_latency_ms: float = 0.0
    subqueries_total: int = 0
    subqueries_successful: int = 0
    subqueries_failed: int = 0
    cache_hits: int = 0
    retries: int = 0
    circuit_breaker_opens: int = 0
    privacy_violations_blocked: int = 0
    sources_used: List[str] = field(default_factory=list)

    @property
    def reliability(self) -> float:
        total = self.subqueries_total
        if total == 0:
            return 0.0
        return self.subqueries_successful / total

    @property
    def efficiency(self) -> float:
        if self.total_latency_ms <= 0:
            return 0.0
        # Placeholder: estimated vs real ratio (simplified)
        return 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_cost": round(self.total_cost, 6),
            "total_latency_ms": round(self.total_latency_ms, 2),
            "subqueries_total": self.subqueries_total,
            "subqueries_successful": self.subqueries_successful,
            "subqueries_failed": self.subqueries_failed,
            "cache_hits": self.cache_hits,
            "retries": self.retries,
            "circuit_breaker_opens": self.circuit_breaker_opens,
            "privacy_violations_blocked": self.privacy_violations_blocked,
            "reliability": round(self.reliability, 4),
            "sources_used": self.sources_used,
        }


@dataclass
class OrquestaResult:
    """Resultado final del orquestador."""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query: str = ""
    answer: Any = None
    confidence: float = 0.0
    verdict: ExecutionVerdict = ExecutionVerdict.FAILED
    subqueries: List[Subquery] = field(default_factory=list)
    resolved_facts: List[ResolvedFact] = field(default_factory=list)
    partial_results: List[PartialResult] = field(default_factory=list)
    context_version_id: Optional[str] = None
    metrics: ExecutionMetrics = field(default_factory=ExecutionMetrics)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "query": self.query,
            "verdict": self.verdict.value,
            "confidence": round(self.confidence, 4),
            "duration_ms": round(self.duration_ms, 2),
            "subqueries_count": len(self.subqueries),
            "resolved_facts_count": len(self.resolved_facts),
            "partial_results_count": len(self.partial_results),
            "metrics": self.metrics.to_dict(),
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "context_version_id": self.context_version_id,
            "subqueries": [s.to_dict() for s in self.subqueries],
            "resolved_facts": [r.to_dict() for r in self.resolved_facts],
            "partial_results": [p.to_dict() for p in self.partial_results[:20]],
        }


@dataclass
class HealthStatus:
    """Estado de salud de una fuente."""
    source_id: str = ""
    healthy: bool = True
    consecutive_failures: int = 0
    last_failure_time: Optional[float] = None
    circuit_open_until: Optional[float] = None
    avg_latency_ms: float = 0.0
    load: int = 0

    @property
    def is_circuit_open(self) -> bool:
        if not self.circuit_open_until:
            return False
        return time.time() < self.circuit_open_until

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "healthy": self.healthy,
            "consecutive_failures": self.consecutive_failures,
            "circuit_open": self.is_circuit_open,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "load": self.load,
        }
