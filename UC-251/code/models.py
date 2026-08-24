"""Modelos de datos para el pipeline RAG de UC-251."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class Document:
    """Documento empresarial ingresado al sistema."""

    doc_id: str
    source: str
    title: str
    content: str
    doc_type: str  # pdf, docx, html, txt, image, ...
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    checksum: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "source": self.source,
            "title": self.title,
            "doc_type": self.doc_type,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "checksum": self.checksum,
            "content_length": len(self.content),
        }


@dataclass
class Chunk:
    """Fragmento semántico de un documento."""

    chunk_id: str
    doc_id: str
    text: str
    index: int
    # Rango de caracteres en el documento original
    start_char: int = 0
    end_char: int = 0
    # Jerarquía: secciones/encabezados a los que pertenece el fragmento
    headings: List[str] = field(default_factory=list)
    # Tipo de contenido: paragraph, table, list, caption, ocr, etc.
    content_type: str = "paragraph"
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Referencias cruzadas detectadas en el texto
    references: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "index": self.index,
            "text": self.text,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "headings": self.headings,
            "content_type": self.content_type,
            "metadata": self.metadata,
            "references": self.references,
        }


@dataclass
class RetrievalResult:
    """Resultado candidato de una etapa de recuperación."""

    chunk: Chunk
    # Scores intermedios (0-1, excepto RRF sin techo)
    vector_score: float = 0.0
    lexical_score: float = 0.0
    hybrid_score: float = 0.0
    rerank_score: Optional[float] = None
    rank_vector: Optional[int] = None
    rank_lexical: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk": self.chunk.to_dict(),
            "vector_score": self.vector_score,
            "lexical_score": self.lexical_score,
            "hybrid_score": self.hybrid_score,
            "rerank_score": self.rerank_score,
            "rank_vector": self.rank_vector,
            "rank_lexical": self.rank_lexical,
        }


@dataclass
class Citation:
    """Cita a un fragmento utilizado en la respuesta generada."""

    chunk_id: str
    doc_id: str
    source: str
    excerpt: str
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "source": self.source,
            "excerpt": self.excerpt,
            "score": self.score,
        }


@dataclass
class RAGResponse:
    """Respuesta completa del sistema RAG."""

    query: str
    answer: str
    citations: List[Citation] = field(default_factory=list)
    retrieved_chunks: List[RetrievalResult] = field(default_factory=list)
    context: str = ""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    generation_model: str = "stub"
    latency_ms: float = 0.0
    insufficient_info: bool = False
    security_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "query": self.query,
            "answer": self.answer,
            "citations": [c.to_dict() for c in self.citations],
            "retrieved_chunks": [r.to_dict() for r in self.retrieved_chunks],
            "context": self.context,
            "generation_model": self.generation_model,
            "latency_ms": round(self.latency_ms, 2),
            "insufficient_info": self.insufficient_info,
            "security_flags": self.security_flags,
        }


@dataclass
class EvaluationSample:
    """Muestra para evaluar el sistema RAG."""

    query: str
    ground_truth: str
    reference_contexts: List[str] = field(default_factory=list)
    expected_doc_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "ground_truth": self.ground_truth,
            "reference_contexts": self.reference_contexts,
            "expected_doc_ids": self.expected_doc_ids,
            "metadata": self.metadata,
        }


@dataclass
class RAGASMetrics:
    """Métricas RAGAS para una muestra o promedio."""

    context_precision: float = 0.0
    context_recall: float = 0.0
    faithfulness: float = 0.0
    answer_relevance: float = 0.0
    answer_correctness: Optional[float] = None

    def average(self, others: List["RAGASMetrics"]) -> "RAGASMetrics":
        if not others:
            return self
        all_metrics = [self] + others
        return RAGASMetrics(
            context_precision=sum(m.context_precision for m in all_metrics) / len(all_metrics),
            context_recall=sum(m.context_recall for m in all_metrics) / len(all_metrics),
            faithfulness=sum(m.faithfulness for m in all_metrics) / len(all_metrics),
            answer_relevance=sum(m.answer_relevance for m in all_metrics) / len(all_metrics),
            answer_correctness=None,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context_precision": round(self.context_precision, 4),
            "context_recall": round(self.context_recall, 4),
            "faithfulness": round(self.faithfulness, 4),
            "answer_relevance": round(self.answer_relevance, 4),
            "answer_correctness": round(self.answer_correctness, 4) if self.answer_correctness is not None else None,
        }


@dataclass
class AuditLog:
    """Registro de auditoría de una consulta RAG."""

    trace_id: str
    timestamp: str
    query: str
    sanitized_query: str
    retrieved_chunk_ids: List[str]
    response_text: str
    latency_ms: float
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    security_flags: List[str] = field(default_factory=list)
    metrics: Optional[RAGASMetrics] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "query": self.query,
            "sanitized_query": self.sanitized_query,
            "retrieved_chunk_ids": self.retrieved_chunk_ids,
            "response_text": self.response_text,
            "latency_ms": round(self.latency_ms, 2),
            "security_flags": self.security_flags,
            "metrics": self.metrics.to_dict() if self.metrics else None,
        }
