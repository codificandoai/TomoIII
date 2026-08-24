"""Evaluación RAGAS: context precision, recall, faithfulness y answer relevance.

Esta implementación ofrece un evaluador heurístico que no requiere API key ni
LLM externo, ideal para tests offline y CI. En producción puede sustituirse por
el paquete oficial `ragas` con LLM-as-a-Judge (OpenAI, Anthropic, local vLLM).
"""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import List, Optional

from models import Chunk, EvaluationSample, RAGASMetrics, RetrievalResult
from text_utils import sentence_split, tokens

logger = logging.getLogger("uc251-ragas")


def _jaccard(a: str, b: str) -> float:
    ta = tokens(a)
    tb = tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def _max_sentence_support(text: str, contexts: List[str], threshold: float = 0.3) -> float:
    """Devuelve la proporción de oraciones de `text` soportadas por algún contexto."""
    sents = sentence_split(text)
    if not sents:
        return 0.0
    supported = 0
    for sent in sents:
        best = max((_jaccard(sent, ctx) for ctx in contexts), default=0.0)
        if best >= threshold:
            supported += 1
    return supported / len(sents)


class BaseRAGASEvaluator(ABC):
    @abstractmethod
    def evaluate(
        self,
        sample: EvaluationSample,
        answer: str,
        retrieved_chunks: List[RetrievalResult],
        context_text: str = "",
    ) -> RAGASMetrics:
        ...


class HeuristicRAGASEvaluator(BaseRAGASEvaluator):
    """Evaluador RAGAS con métricas basadas en solapamiento léxico."""

    RELEVANCE_THRESHOLD = 0.15
    SUPPORT_THRESHOLD = 0.25

    def evaluate(
        self,
        sample: EvaluationSample,
        answer: str,
        retrieved_chunks: List[RetrievalResult],
        context_text: str = "",
    ) -> RAGASMetrics:
        contexts = [r.chunk.text for r in retrieved_chunks]
        # Context precision: % de chunks recuperados relevantes para la respuesta/pregunta
        relevant = 0
        for chunk_text in contexts:
            sim_answer = _jaccard(chunk_text, answer)
            sim_question = _jaccard(chunk_text, sample.query)
            sim_ground = _jaccard(chunk_text, sample.ground_truth)
            if max(sim_answer, sim_question, sim_ground) >= self.RELEVANCE_THRESHOLD:
                relevant += 1
        context_precision = relevant / len(contexts) if contexts else 0.0

        # Context recall: % de oraciones del ground truth soportadas por algún chunk
        gt_sents = sentence_split(sample.ground_truth)
        recall_hits = 0
        for gt in gt_sents:
            best = max((_jaccard(gt, ctx) for ctx in contexts), default=0.0)
            if best >= self.SUPPORT_THRESHOLD:
                recall_hits += 1
        context_recall = recall_hits / len(gt_sents) if gt_sents else 1.0

        # Faithfulness: % de oraciones de la respuesta soportadas por el contexto
        faithfulness = _max_sentence_support(answer, contexts, threshold=self.SUPPORT_THRESHOLD)

        # Answer relevance: similitud pregunta-respuesta, penalizando respuesta de insuficiencia
        answer_relevance = _jaccard(answer, sample.query)
        if "no dispongo de información suficiente" in answer.lower() or not contexts:
            answer_relevance = 0.0

        return RAGASMetrics(
            context_precision=round(context_precision, 4),
            context_recall=round(context_recall, 4),
            faithfulness=round(faithfulness, 4),
            answer_relevance=round(answer_relevance, 4),
        )


class OpenAIRAGASEvaluator(BaseRAGASEvaluator):
    """Punto de extensión para usar el paquete oficial `ragas` con OpenAI."""

    def evaluate(
        self,
        sample: EvaluationSample,
        answer: str,
        retrieved_chunks: List[RetrievalResult],
        context_text: str = "",
    ) -> RAGASMetrics:
        raise NotImplementedError(
            "Instale el paquete `ragas` y configure OPENAI_API_KEY para usar "
            "el evaluador basado en LLM-as-a-Judge."
        )


def build_ragas_evaluator(provider: str) -> BaseRAGASEvaluator:
    if provider.lower() == "openai":
        return OpenAIRAGASEvaluator()
    return HeuristicRAGASEvaluator()
