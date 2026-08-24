"""Orquestador del pipeline RAG: ingesta -> indexación -> recuperación -> generación."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from audit_logger import AuditLogger
from chunker import DeduplicatedChunker, SemanticChunker
from config import RAGConfig
from context_assembler import ContextAssembler
from document_parser import DocumentParser
from embedder import BaseEmbedder, build_embedder
from generator import BaseLLMClient, PromptBuilder, build_llm_client
from lexical_store import BM25Index
from models import AuditLog, EvaluationSample, RAGASMetrics, RAGResponse, RetrievalResult
from ragas_evaluator import build_ragas_evaluator
from reranker import BaseReranker, build_reranker
from retriever import HybridRetriever
from security import SecurityChecker
from vector_store import BaseVectorStore, build_vector_store

logger = logging.getLogger("uc251-pipeline")


class RAGPipeline:
    """Pipeline completo RAG con auditoría y evaluación."""

    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or RAGConfig()
        self.embedder: BaseEmbedder = build_embedder(self.config.embedder)
        self.vector_store: BaseVectorStore = build_vector_store(self.config.vector_store)
        self.lexical_store = BM25Index(self.config.lexical)
        self.retriever = HybridRetriever(
            self.vector_store,
            self.lexical_store,
            self.embedder,
            self.config.retrieval,
            self.config.security,
        )
        self.reranker: BaseReranker = build_reranker(self.config.reranker)
        self.assembler = ContextAssembler(self.config.retrieval)
        self.generator: BaseLLMClient = build_llm_client(self.config.generator)
        self.security = SecurityChecker(self.config.security)
        self.audit = AuditLogger(self.config, self.security)
        self.evaluator = build_ragas_evaluator(self.config.evaluation.judge_provider)
        self.parser = DocumentParser()
        self.chunker = DeduplicatedChunker(
            SemanticChunker(self.config.chunking, self.embedder)
        )
        self._ingested_docs: Dict[str, Dict[str, Any]] = {}

    def ingest_document(
        self,
        source: str,
        doc_type: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Ingesta un archivo o texto plano, lo fragmenta e indexa."""
        metadata = metadata or {}
        doc = self.parser.parse(source, doc_type=doc_type, title=title, metadata=metadata)
        chunks = self.chunker.chunk(doc)
        if not chunks:
            logger.warning("No se generaron chunks para %s", source)
            return {"doc_id": doc.doc_id, "num_chunks": 0, "document": doc.to_dict()}

        texts = [c.text for c in chunks]
        embeddings = self.embedder.embed_texts(texts)
        self.vector_store.add_chunks(chunks, np.array(embeddings, dtype="float32"))
        self.lexical_store.add_chunks(chunks)

        self._ingested_docs[doc.doc_id] = {
            "document": doc.to_dict(),
            "chunks": [c.to_dict() for c in chunks],
        }
        logger.info("Ingestado doc_id=%s chunks=%d", doc.doc_id, len(chunks))
        return {"doc_id": doc.doc_id, "num_chunks": len(chunks), "document": doc.to_dict()}

    def ingest_text(
        self,
        text: str,
        title: str = "inline",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.ingest_document(text, doc_type="txt", title=title, metadata=metadata)

    def query(
        self,
        question: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
        user_clearance: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> RAGResponse:
        """Ejecuta una consulta end-to-end con auditoría."""
        start = time.time()
        security = self.security.check(question)
        if security.blocked:
            return RAGResponse(
                query=question,
                answer="La consulta ha sido bloqueada por seguridad.",
                security_flags=security.flags,
                latency_ms=(time.time() - start) * 1000,
                insufficient_info=False,
            )

        clean_question = security.sanitized
        filters = filters or {}
        if tenant_id:
            filters.setdefault("tenant_id", tenant_id)

        candidates = self.retriever.retrieve(
            clean_question,
            top_k=self.config.retrieval.rerank_candidates,
            filters=filters,
            user_clearance=user_clearance,
        )
        reranked = self.reranker.rerank(clean_question, candidates)
        context, selected = self.assembler.assemble(reranked)

        answer, citations, insufficient = self.generator.generate(
            clean_question, context, selected, self.config.generator
        )

        latency_ms = (time.time() - start) * 1000
        response = RAGResponse(
            query=question,
            answer=answer,
            citations=citations,
            retrieved_chunks=selected,
            context=context,
            latency_ms=latency_ms,
            insufficient_info=insufficient,
            security_flags=security.flags,
            generation_model=self.config.generator.model_name,
        )
        self.audit.log(
            query=question,
            response=response,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        return response

    def evaluate(
        self,
        samples: List[EvaluationSample],
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Evalúa el pipeline con métricas RAGAS sobre un conjunto de muestras."""
        per_sample = []
        for sample in samples:
            response = self.query(
                sample.query,
                filters=sample.metadata.get("filters") if sample.metadata else None,
                tenant_id=tenant_id,
            )
            context_text = response.context
            metrics = self.evaluator.evaluate(
                sample, response.answer, response.retrieved_chunks, context_text
            )
            self.audit.log(
                query=sample.query,
                response=response,
                tenant_id=tenant_id,
                user_id="evaluator",
                metrics=metrics,
            )
            per_sample.append(
                {
                    "query": sample.query,
                    "ground_truth": sample.ground_truth,
                    "answer": response.answer,
                    "metrics": metrics.to_dict(),
                    "trace_id": response.trace_id,
                    "retrieved_chunk_ids": [
                        r.chunk.chunk_id for r in response.retrieved_chunks
                    ],
                }
            )
        avg = self._average_from_dicts([s["metrics"] for s in per_sample])
        return {
            "samples": per_sample,
            "average_metrics": avg.to_dict(),
            "total_samples": len(samples),
        }

    @staticmethod
    def _average_from_dicts(metrics_dicts: List[Dict[str, Any]]) -> RAGASMetrics:
        if not metrics_dicts:
            return RAGASMetrics()
        keys = ["context_precision", "context_recall", "faithfulness", "answer_relevance"]
        return RAGASMetrics(
            context_precision=sum(m.get(keys[0], 0.0) for m in metrics_dicts) / len(metrics_dicts),
            context_recall=sum(m.get(keys[1], 0.0) for m in metrics_dicts) / len(metrics_dicts),
            faithfulness=sum(m.get(keys[2], 0.0) for m in metrics_dicts) / len(metrics_dicts),
            answer_relevance=sum(m.get(keys[3], 0.0) for m in metrics_dicts) / len(metrics_dicts),
        )

    def get_stats(self) -> Dict[str, Any]:
        return {
            "documents_indexed": len(self._ingested_docs),
            "chunks_indexed": self.vector_store.count(),
            "vector_backend": self.config.vector_store.backend,
            "embedder_model": self.config.embedder.model_name,
            "generator_provider": self.config.generator.provider,
            "audit_logs_in_memory": len(self.audit._logs),
        }
