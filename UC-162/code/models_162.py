"""
UC-162 — Modelos de datos para LLMOps.

Define configuración, esquema lógico, documentos, chunks, embeddings,
prompts, resultados de verificación de sesgo, linaje semántico,
hallucination, drift conceptual y decisiones del guardian LLMOps.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
import time
import uuid


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BiasControlType(Enum):
    """Tipos de control de sesgo en el modelado lógico."""
    DEMOGRAPHIC = "demographic"
    PERSPECTIVE = "perspective"
    TEMPORAL = "temporal"
    SOURCE = "source"
    LANGUAGE = "language"


class BiasAction(Enum):
    """Acciones ante detección de sesgo."""
    PASS = "pass"
    FLAG = "flag_for_review"
    REJECT = "reject_lot"
    ENRICH = "enrich_with_complementary_sources"


class LineageStage(Enum):
    """Etapas del linaje semántico."""
    INGEST = "ingest"
    CLEAN = "clean"
    CHUNK = "chunk"
    EMBED = "embed"
    INDEX = "index"
    RETRIEVE = "retrieve"
    GENERATE = "generate"


class LLMOpsDecision(Enum):
    """Decisión final del guardian LLMOps."""
    APPROVE = "approve"
    FLAG = "flag"
    REJECT = "reject"
    ESCALATE = "escalate"


class HallucinationSeverity(Enum):
    """Severidad de hallucination detectada."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DriftType(Enum):
    """Tipos de drift conceptual."""
    NONE = "none"
    SEMANTIC = "semantic"
    CONTEXTUAL = "contextual"
    TEMPORAL = "temporal"
    COMBINED = "combined"


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

@dataclass
class BiasThreshold:
    """Umbral de sesgo para un campo del esquema lógico."""
    field_name: str
    max_dominance: float = 0.70
    min_representation: float = 0.0
    action_if_exceeds: str = "flag_for_review"
    action_if_missing: str = "enrich_with_complementary_sources"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_name": self.field_name,
            "max_dominance": self.max_dominance,
            "min_representation": self.min_representation,
            "action_if_exceeds": self.action_if_exceeds,
            "action_if_missing": self.action_if_missing,
        }


@dataclass
class LLMOpsConfig:
    """Configuración de la capa LLMOps."""
    # Sesgo
    max_demographic_dominance: float = 0.70
    max_region_dominance: float = 0.60
    max_perspective_dominance: float = 0.80
    min_perspective_representation: float = 0.10
    max_temporal_dominance: float = 0.65
    max_source_type_dominance: float = 0.75
    max_language_dominance: float = 0.95
    # Linaje
    require_lineage_hash: bool = True
    lineage_hash_algorithm: str = "sha256"
    # Hallucination
    hallucination_entropy_threshold: float = 0.85
    hallucination_coverage_threshold: float = 0.60
    hallucination_contradiction_threshold: float = 0.30
    # Drift conceptual
    drift_semantic_threshold: float = 0.25
    drift_temporal_window_days: int = 30
    # Prompt versioning
    max_prompt_versions: int = 50
    require_prompt_approval: bool = True
    # General
    min_documents_for_bias_check: int = 5
    component: str = "uc162_llmops"
    pipeline: str = "uc162_llmops"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_demographic_dominance": self.max_demographic_dominance,
            "max_region_dominance": self.max_region_dominance,
            "max_perspective_dominance": self.max_perspective_dominance,
            "min_perspective_representation": self.min_perspective_representation,
            "max_temporal_dominance": self.max_temporal_dominance,
            "max_source_type_dominance": self.max_source_type_dominance,
            "max_language_dominance": self.max_language_dominance,
            "require_lineage_hash": self.require_lineage_hash,
            "lineage_hash_algorithm": self.lineage_hash_algorithm,
            "hallucination_entropy_threshold": self.hallucination_entropy_threshold,
            "hallucination_coverage_threshold": self.hallucination_coverage_threshold,
            "hallucination_contradiction_threshold": self.hallucination_contradiction_threshold,
            "drift_semantic_threshold": self.drift_semantic_threshold,
            "drift_temporal_window_days": self.drift_temporal_window_days,
            "max_prompt_versions": self.max_prompt_versions,
            "require_prompt_approval": self.require_prompt_approval,
            "min_documents_for_bias_check": self.min_documents_for_bias_check,
            "component": self.component,
            "pipeline": self.pipeline,
        }


# ---------------------------------------------------------------------------
# Entidades del modelado lógico
# ---------------------------------------------------------------------------

@dataclass
class DocumentMetadata:
    """Metadatos de gobernanza de un documento del corpus."""
    id_documento: str = ""
    fuente: str = ""
    fuente_tipo: str = ""  # academica, gubernamental, corporativa, crowd
    fecha_creacion: str = ""
    categoria_tema: str = ""
    genero_autor: str = ""
    region_geografica: str = ""
    perspectiva_tematica: str = ""  # tecnica, legal, etica, economica, social
    idioma: str = ""
    variante_regional: str = ""
    contexto_cultural: str = ""
    nivel_confianza: float = 0.5
    periodo_temporal: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id_documento": self.id_documento,
            "fuente": self.fuente,
            "fuente_tipo": self.fuente_tipo,
            "fecha_creacion": self.fecha_creacion,
            "categoria_tema": self.categoria_tema,
            "genero_autor": self.genero_autor,
            "region_geografica": self.region_geografica,
            "perspectiva_tematica": self.perspectiva_tematica,
            "idioma": self.idioma,
            "variante_regional": self.variante_regional,
            "contexto_cultural": self.contexto_cultural,
            "nivel_confianza": self.nivel_confianza,
            "periodo_temporal": self.periodo_temporal,
        }


@dataclass
class CorpusDocument:
    """Documento del corpus con texto y metadatos de gobernanza."""
    id: str
    text: str
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "metadata": self.metadata.to_dict(),
        }


@dataclass
class Chunk:
    """Fragmento de un documento con contexto preservado."""
    id: str
    document_id: str
    text: str
    start_char: int = 0
    end_char: int = 0
    strategy: str = "fixed"  # fixed, semantic, recursive
    size: int = 0
    overlap: int = 0
    parent_hash: str = ""
    hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "text": self.text,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "strategy": self.strategy,
            "size": self.size,
            "overlap": self.overlap,
            "parent_hash": self.parent_hash,
            "hash": self.hash,
        }


@dataclass
class EmbeddingRecord:
    """Registro de embedding con metadatos de generación."""
    chunk_id: str
    vector: List[float]
    model: str = "text-embedding-3"
    dimension: int = 0
    generated_at: str = ""
    parent_hash: str = ""
    hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "vector_dim": len(self.vector),
            "model": self.model,
            "dimension": self.dimension,
            "generated_at": self.generated_at,
            "parent_hash": self.parent_hash,
            "hash": self.hash,
        }


@dataclass
class PromptVersion:
    """Versión de un prompt template con metadatos de aprobación."""
    id: str
    template: str
    version: str
    approved: bool = False
    approved_by: str = ""
    created_at: float = field(default_factory=time.time)
    evaluation_score: float = 0.0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "template": self.template,
            "version": self.version,
            "approved": self.approved,
            "approved_by": self.approved_by,
            "created_at": self.created_at,
            "evaluation_score": self.evaluation_score,
            "tags": self.tags,
        }


# ---------------------------------------------------------------------------
# Reportes
# ---------------------------------------------------------------------------

@dataclass
class BiasCheck:
    """Resultado de un control de sesgo individual."""
    control_type: str
    field_name: str
    dominance: float
    threshold: float
    action: str
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "control_type": self.control_type,
            "field_name": self.field_name,
            "dominance": self.dominance,
            "threshold": self.threshold,
            "action": self.action,
            "passed": self.passed,
            "details": self.details,
        }


@dataclass
class BiasReport:
    """Reporte completo de verificación de sesgo."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    all_passed: bool = True
    checks: List[BiasCheck] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "all_passed": self.all_passed,
            "checks": [c.to_dict() for c in self.checks],
            "actions": self.actions,
            "metrics": self.metrics,
        }


@dataclass
class LineageNode:
    """Nodo del grafo de linaje semántico."""
    node_id: str
    stage: str
    entity_id: str
    hash: str
    parent_hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "stage": self.stage,
            "entity_id": self.entity_id,
            "hash": self.hash,
            "parent_hash": self.parent_hash,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class LineageGraph:
    """Grafo de linaje semántico completo."""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    nodes: List[LineageNode] = field(default_factory=list)
    edges: List[Dict[str, str]] = field(default_factory=list)

    def add_node(self, node: LineageNode):
        self.nodes.append(node)
        if node.parent_hash:
            self.edges.append({
                "from": node.parent_hash,
                "to": node.hash,
                "stage": node.stage,
            })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": self.edges,
        }


@dataclass
class HallucinationReport:
    """Reporte de detección de hallucination."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    timestamp: float = field(default_factory=time.time)
    severity: str = "none"
    is_hallucination: bool = False
    coverage_score: float = 0.0
    contradiction_score: float = 0.0
    entropy_score: float = 0.0
    unsupported_claims: List[str] = field(default_factory=list)
    flagged_chunks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "severity": self.severity,
            "is_hallucination": self.is_hallucination,
            "coverage_score": self.coverage_score,
            "contradiction_score": self.contradiction_score,
            "entropy_score": self.entropy_score,
            "unsupported_claims": self.unsupported_claims,
            "flagged_chunks": self.flagged_chunks,
        }


@dataclass
class DriftReport:
    """Reporte de drift conceptual."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    timestamp: float = field(default_factory=time.time)
    drift_type: str = "none"
    drift_score: float = 0.0
    threshold: float = 0.25
    is_drift: bool = False
    baseline_concept: str = ""
    current_concept: str = ""
    affected_features: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "drift_type": self.drift_type,
            "drift_score": self.drift_score,
            "threshold": self.threshold,
            "is_drift": self.is_drift,
            "baseline_concept": self.baseline_concept,
            "current_concept": self.current_concept,
            "affected_features": self.affected_features,
            "details": self.details,
        }


@dataclass
class LLMOpsResult:
    """Resultado completo del guardian LLMOps."""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    decision: str = "approve"
    bias_report: Optional[Dict[str, Any]] = None
    lineage_graph: Optional[Dict[str, Any]] = None
    hallucination_report: Optional[Dict[str, Any]] = None
    drift_report: Optional[Dict[str, Any]] = None
    prompt_version: Optional[Dict[str, Any]] = None
    issues: List[str] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "decision": self.decision,
            "bias_report": self.bias_report,
            "lineage_graph": self.lineage_graph,
            "hallucination_report": self.hallucination_report,
            "drift_report": self.drift_report,
            "prompt_version": self.prompt_version,
            "issues": self.issues,
            "duration_ms": self.duration_ms,
        }
