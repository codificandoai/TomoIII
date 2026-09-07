"""
UC-326 — Módulo Critic para MAQRI.

Evalúa si los documentos recuperados responden realmente a la pregunta.
Identifica:
- Score de relevancia (overlap con query).
- Score de cobertura (diversidad de aspectos).
- Score de novedad (información nueva vs. working memory).
- Información faltante.
- Razón de fracaso.
- Confianza global.
"""

from typing import List, Dict, Optional, Set

from maqri_models import RetrievedDocument, CriticAssessment, WorkingMemory


class CriticEvaluator:
    """
    Módulo 'Critic' de MAQRI.

    Determina si la información recuperada es suficiente y de calidad,
    y si no lo es, articula QUÉ falta y POR QUÉ la consulta falló.
    """

    def __init__(
        self,
        relevance_threshold: float = 0.5,
        coverage_threshold: float = 0.4,
        novelty_threshold: float = 0.3,
    ):
        self.relevance_threshold = relevance_threshold
        self.coverage_threshold = coverage_threshold
        self.novelty_threshold = novelty_threshold

    def evaluate(
        self,
        query: str,
        docs: List[RetrievedDocument],
        working_memory: Optional[WorkingMemory] = None,
    ) -> CriticAssessment:
        """
        Evalúa un conjunto de documentos recuperados contra el query.

        Retorna CriticAssessment con scores, información faltante y
        razón de fracaso (si aplica).
        """
        wm = working_memory or WorkingMemory()

        relevance = self._evaluate_relevance(query, docs)
        coverage = self._evaluate_coverage(docs)
        novelty = self._evaluate_novelty(docs, wm)

        missing_info = ""
        failure_reason = ""
        confidence = 0.0

        if relevance >= self.relevance_threshold and coverage >= self.coverage_threshold:
            confidence = min(1.0, (relevance + coverage + novelty) / 3 + 0.2)
            if novelty < self.novelty_threshold and wm.accumulated_facts:
                missing_info = "No new information compared to working memory"
                failure_reason = "Retrieval returned mostly redundant facts"
                confidence *= 0.8
        else:
            confidence = max(0.1, (relevance + coverage + novelty) / 3)
            if relevance < self.relevance_threshold:
                missing_info = "Documents are not sufficiently relevant to the query"
                failure_reason = "Query did not retrieve focused information"
            elif coverage < self.coverage_threshold:
                missing_info = "Missing aspects of the query topic"
                failure_reason = "Query was too narrow or missed key dimensions"

        return CriticAssessment(
            relevance_score=round(relevance, 4),
            coverage_score=round(coverage, 4),
            novelty_score=round(novelty, 4),
            missing_info=missing_info,
            failure_reason=failure_reason,
            confidence=round(confidence, 4),
        )

    def _evaluate_relevance(self, query: str, docs: List[RetrievedDocument]) -> float:
        """Evalúa relevancia promedio de documentos al query."""
        if not docs or not query:
            return 0.0

        query_words = set(query.lower().split())
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "of", "in", "to",
            "and", "or", "not", "it", "this", "that", "for", "with", "on",
            "el", "la", "los", "las", "de", "en", "un", "una", "y", "o", "con",
        }
        query_words -= stop_words

        if not query_words:
            return 0.0

        scores = []
        for doc in docs:
            doc_words = set(doc.content.lower().split()) - stop_words
            if not doc_words:
                continue
            intersection = len(query_words & doc_words)
            union = len(query_words | doc_words)
            jaccard = intersection / union if union > 0 else 0.0
            scores.append(jaccard)

        return sum(scores) / len(scores) if scores else 0.0

    def _evaluate_coverage(self, docs: List[RetrievedDocument]) -> float:
        """Evalúa cobertura temática usando diversidad de contenido."""
        if not docs:
            return 0.0

        if len(docs) == 1:
            return 0.4  # Cobertura parcial

        # Diversidad promedio (Jaccard distance)
        total_distance = 0.0
        pairs = 0
        for i, d1 in enumerate(docs):
            w1 = set(d1.content.lower().split())
            for d2 in docs[i + 1:]:
                w2 = set(d2.content.lower().split())
                if not w1 or not w2:
                    continue
                intersection = len(w1 & w2)
                union = len(w1 | w2)
                jaccard = intersection / union if union > 0 else 0.0
                total_distance += (1.0 - jaccard)
                pairs += 1

        return total_distance / pairs if pairs > 0 else 0.0

    def _evaluate_novelty(
        self,
        docs: List[RetrievedDocument],
        working_memory: WorkingMemory,
    ) -> float:
        """Evalúa qué tanto los documentos aportan información nueva."""
        if not docs:
            return 0.0

        known_facts: Set[str] = set()
        for fact in working_memory.accumulated_facts:
            known_facts.add(" ".join(fact.lower().split()))

        if not known_facts:
            return 1.0  # Todo es nuevo

        new_count = 0
        for doc in docs:
            normalized = " ".join(doc.content.lower().split())
            if normalized not in known_facts:
                new_count += 1

        return new_count / len(docs)

    def should_continue(self, assessment: CriticAssessment) -> bool:
        """Decide si se necesita otra iteración de retrieval."""
        if assessment.confidence >= 0.85:
            return False
        if not assessment.failure_reason:
            return False
        return True

    def get_feedback(
        self,
        assessment: CriticAssessment,
    ) -> Dict[str, str]:
        """Retorna feedback estructurado para el refiner."""
        return {
            "missing_info": assessment.missing_info,
            "failure_reason": assessment.failure_reason,
            "relevance": f"{assessment.relevance_score:.3f}",
            "coverage": f"{assessment.coverage_score:.3f}",
            "novelty": f"{assessment.novelty_score:.3f}",
            "confidence": f"{assessment.confidence:.3f}",
        }
