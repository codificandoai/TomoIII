"""Recuperación híbrida: BM25 + vectorial fusionados con RRF."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from config import RetrievalConfig, SecurityConfig
from embedder import BaseEmbedder
from lexical_store import BM25Index
from models import Chunk, RetrievalResult
from vector_store import BaseVectorStore

logger = logging.getLogger("uc251-retriever")


def _level_value(level: str, levels: List[str]) -> int:
    try:
        return levels.index(level)
    except ValueError:
        return 0


def build_metadata_filter(
    filters: Dict[str, Any],
    security: SecurityConfig,
    user_clearance: Optional[str] = None,
) -> Optional[Callable[[Chunk], bool]]:
    """Construye función de filtrado por metadatos, permisos y confidencialidad."""
    predicates = []

    tenant_id = filters.get("tenant_id")
    if tenant_id:
        predicates.append(lambda c, tid=tenant_id: c.metadata.get("tenant_id") == tid)

    doc_types = filters.get("doc_type")
    if doc_types:
        allowed = set(doc_types) if isinstance(doc_types, list) else {doc_types}
        predicates.append(lambda c, allowed=allowed: c.metadata.get("doc_type") in allowed)

    date_from = filters.get("date_from")
    date_to = filters.get("date_to")
    if date_from or date_to:
        def _date_ok(c):
            created = c.metadata.get("created_at") or c.metadata.get("date")
            if not created:
                return True
            try:
                dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            except Exception:
                return True
            if date_from:
                try:
                    df = datetime.fromisoformat(str(date_from).replace("Z", "+00:00"))
                    if dt < df:
                        return False
                except Exception:
                    pass
            if date_to:
                try:
                    dte = datetime.fromisoformat(str(date_to).replace("Z", "+00:00"))
                    if dt > dte:
                        return False
                except Exception:
                    pass
            return True
        predicates.append(_date_ok)

    if user_clearance:
        user_level = _level_value(user_clearance, security.confidentiality_levels)
        def _clearance_ok(c):
            doc_level = c.metadata.get("confidentiality", "public")
            return _level_value(doc_level, security.confidentiality_levels) <= user_level
        predicates.append(_clearance_ok)

    if not predicates:
        return None

    def _filter(chunk: Chunk) -> bool:
        return all(p(chunk) for p in predicates)

    return _filter


class HybridRetriever:
    """Combina búsqueda léxica (BM25) y semántica (vectorial) con RRF."""

    def __init__(
        self,
        vector_store: BaseVectorStore,
        lexical_store: BM25Index,
        embedder: BaseEmbedder,
        config: RetrievalConfig,
        security: SecurityConfig,
    ):
        self.vector_store = vector_store
        self.lexical_store = lexical_store
        self.embedder = embedder
        self.config = config
        self.security = security

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        user_clearance: Optional[str] = None,
    ) -> List[RetrievalResult]:
        filters = filters or {}
        top_k = top_k or self.config.final_context_chunks * 4
        filter_fn = build_metadata_filter(filters, self.security, user_clearance)

        # --- Vector ---
        q_vec = self.embedder.embed_text(query)
        import numpy as np
        vec_results = self.vector_store.search(
            np.array(q_vec, dtype="float32"),
            top_k=self.config.top_k_vector,
            filter_fn=filter_fn,
        )

        # --- Lexical ---
        lex_results = self.lexical_store.search(
            query,
            top_k=self.config.top_k_lexical,
            filter_fn=filter_fn,
        )

        # --- RRF fusion ---
        scores: Dict[str, RetrievalResult] = {}
        k = self.config.rrf_k
        for rank, (chunk, score) in enumerate(vec_results, start=1):
            existing = scores.get(chunk.chunk_id)
            if existing is None:
                existing = RetrievalResult(chunk=chunk)
                scores[chunk.chunk_id] = existing
            existing.vector_score = score
            existing.rank_vector = rank
            existing.hybrid_score += 1.0 / (k + rank)

        for rank, (chunk, score) in enumerate(lex_results, start=1):
            existing = scores.get(chunk.chunk_id)
            if existing is None:
                existing = RetrievalResult(chunk=chunk)
                scores[chunk.chunk_id] = existing
            existing.lexical_score = score
            existing.rank_lexical = rank
            existing.hybrid_score += 1.0 / (k + rank)

        results = sorted(
            scores.values(),
            key=lambda r: (
                r.hybrid_score,
                r.vector_score,
                r.lexical_score,
            ),
            reverse=True,
        )
        min_thr = self.config.min_score_threshold
        results = [r for r in results if r.hybrid_score >= min_thr]
        return results[:top_k]
