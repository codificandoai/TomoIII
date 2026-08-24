"""Re-ranking de candidatos mediante cross-encoder real o stub léxico."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List

from config import RerankerConfig
from models import RetrievalResult
from text_utils import tokens

logger = logging.getLogger("uc251-reranker")


class BaseReranker(ABC):
    @abstractmethod
    def rerank(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]:
        ...


class StubReranker(BaseReranker):
    """Re-ranker determinista basado en solapamiento léxico.

    En producción sustituir por un cross-encoder como BGE-Reranker o Cohere.
    """

    def rerank(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]:
        q_tokens = tokens(query)
        if not q_tokens:
            return results
        scored = []
        for res in results:
            ct = tokens(res.chunk.text)
            inter = len(q_tokens & ct)
            union = len(q_tokens | ct)
            score = inter / union if union else 0.0
            # ponderar también la confianza híbrida previa
            score = 0.7 * score + 0.3 * min(res.hybrid_score, 1.0)
            res.rerank_score = round(score, 6)
            scored.append(res)
        scored.sort(key=lambda r: (r.rerank_score or 0.0, r.hybrid_score), reverse=True)
        return scored


class SentenceTransformerReranker(BaseReranker):
    """Cross-encoder basado en sentence-transformers."""

    def __init__(self, config: RerankerConfig):
        self.config = config
        try:
            from sentence_transformers import CrossEncoder
        except Exception as exc:  # pragma: no cover
            raise ImportError(
                "sentence-transformers no está instalado. Use StubReranker."
            ) from exc
        logger.info("Cargando cross-encoder: %s", config.model_name)
        self.model = CrossEncoder(config.model_name)

    def rerank(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]:
        if not results:
            return results
        pairs = [[query, r.chunk.text] for r in results]
        scores = self.model.predict(pairs, show_progress_bar=False)
        for res, score in zip(results, scores):
            res.rerank_score = float(score)
        results.sort(key=lambda r: (r.rerank_score or 0.0, r.hybrid_score), reverse=True)
        return results


def build_reranker(config: RerankerConfig) -> BaseReranker:
    if config.model_name == "stub":
        return StubReranker()
    return SentenceTransformerReranker(config)
