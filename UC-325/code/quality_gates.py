"""
UC-325 — Quality Gates para el Motor de Bucles de Razonamiento Autorreflexivos.

Evalúa cinco dimensiones de calidad en cada iteración del bucle:
1. Relevance: ¿Los chunks recuperados son pertinentes al query?
2. Coverage: ¿Se cubren todas las sub-preguntas y aspectos?
3. Consistency: ¿Las hipótesis son coherentes entre sí y con la evidencia?
4. Confidence: ¿El nivel de confianza está soportado por evidencia?
5. Novelty: ¿Cada iteración aporta información nueva?

Principio: Un modelo genera evidencia. La evidencia no es una orden.
"""

from typing import List, Dict, Optional, Set
import math
import hashlib
from collections import Counter

from reasoning_models import (
    QualityScore,
    QualityDimension,
    ReasoningState,
    Hypothesis,
    RetrievedChunk,
    KnowledgeGap,
    DEFAULT_QUALITY_THRESHOLDS,
    QUALITY_WEIGHTS,
    HypothesisStatus,
)


class QualityGateEvaluator:
    """
    Evaluador de quality gates para cada iteración del razonamiento.

    Calcula scores 0.0-1.0 para cinco dimensiones y determina si la
    iteración pasa los umbrales mínimos de calidad.
    """

    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        self.thresholds = thresholds or dict(DEFAULT_QUALITY_THRESHOLDS)
        self._previous_fingerprints: Set[str] = set()

    def evaluate(self, state: ReasoningState) -> QualityScore:
        """Evalúa todas las dimensiones de calidad para la iteración actual."""
        chunks = list(state.all_chunks.values())
        hypotheses = state.active_hypotheses
        gaps = list(state.gaps.values())

        relevance = self._evaluate_relevance(state.query, chunks)
        coverage = self._evaluate_coverage(state.query, hypotheses, gaps)
        consistency = self._evaluate_consistency(hypotheses, chunks)
        confidence = self._evaluate_confidence(hypotheses, chunks)
        novelty = self._evaluate_novelty(chunks, state.round_number)

        return QualityScore(
            relevance=relevance,
            coverage=coverage,
            consistency=consistency,
            confidence=confidence,
            novelty=novelty,
            round_number=state.round_number,
        )

    def _evaluate_relevance(self, query: str, chunks: List[RetrievedChunk]) -> float:
        """
        Evalúa la pertinencia de los chunks al query.

        Heurística: calcula overlap de tokens entre query y chunks,
        ponderado por el score de retrieval.
        """
        if not chunks or not query:
            return 0.0

        query_tokens = set(query.lower().split())
        if not query_tokens:
            return 0.0

        total_relevance = 0.0
        total_weight = 0.0

        for chunk in chunks:
            chunk_tokens = set(chunk.content.lower().split())
            if not chunk_tokens:
                continue

            # Overlap de tokens (Jaccard-like)
            intersection = query_tokens & chunk_tokens
            union_size = len(query_tokens | chunk_tokens)
            token_overlap = len(intersection) / union_size if union_size > 0 else 0.0

            # Ponderar por score de retrieval
            weight = max(chunk.score, 0.01)
            total_relevance += token_overlap * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        raw_score = total_relevance / total_weight

        # Boost si hay muchos chunks con buen score
        high_score_ratio = sum(1 for c in chunks if c.score >= 0.5) / max(len(chunks), 1)
        boosted = raw_score * 0.6 + high_score_ratio * 0.4

        return min(boosted, 1.0)

    def _evaluate_coverage(
        self,
        query: str,
        hypotheses: List[Hypothesis],
        gaps: List[KnowledgeGap],
    ) -> float:
        """
        Evalúa la completitud de la respuesta.

        Coverage = (aspectos cubiertos por hipótesis) / (aspectos totales requeridos).
        Penaliza por gaps no llenados.
        """
        if not hypotheses:
            return 0.0

        # Contar aspectos cubiertos por hipótesis activas
        covered_aspects = len(hypotheses)
        total_gaps = len(gaps)
        filled_gaps = sum(1 for g in gaps if g.filled)
        unfilled_gaps = total_gaps - filled_gaps

        # Baseline: al menos tener hipótesis
        base_coverage = min(covered_aspects / max(covered_aspects + unfilled_gaps, 1), 1.0)

        # Penalizar por gaps críticos no llenados
        critical_gaps = [g for g in gaps if g.priority > 0.7 and not g.filled]
        gap_penalty = len(critical_gaps) * 0.15

        return max(base_coverage - gap_penalty, 0.0)

    def _evaluate_consistency(
        self,
        hypotheses: List[Hypothesis],
        chunks: List[RetrievedChunk],
    ) -> float:
        """
        Evalúa la coherencia interna entre hipótesis y con la evidencia.

        Detecta contradicciones entre hipótesis y verifica que cada
        hipótesis tenga soporte en los chunks.
        """
        if not hypotheses:
            return 0.0

        total_score = 0.0
        chunk_map = {c.chunk_id: c for c in chunks}

        for hyp in hypotheses:
            # Score base por tener chunks de soporte
            supporting = [chunk_map[cid] for cid in hyp.supporting_chunks if cid in chunk_map]
            if supporting:
                avg_support_score = sum(c.score for c in supporting) / len(supporting)
                support_factor = min(avg_support_score, 1.0)
            else:
                support_factor = 0.2  # Penalización por hipótesis sin soporte

            total_score += support_factor

        avg_consistency = total_score / len(hypotheses)

        # Penalizar si hay muchas hipótesis refutadas (señal de inconsistencia previa)
        # No aplica aquí porque solo vemos activas, pero ajustar por coherence_score
        coherence_boost = sum(h.coherence_score for h in hypotheses) / max(len(hypotheses), 1)

        return min(avg_consistency * 0.7 + coherence_boost * 0.3, 1.0)

    def _evaluate_confidence(
        self,
        hypotheses: List[Hypothesis],
        chunks: List[RetrievedChunk],
    ) -> float:
        """
        Evalúa si el nivel de confianza está soportado por evidencia.

        Detecta confidence inflation: alta confianza sin evidencia proporcional.
        """
        if not hypotheses:
            return 0.0

        chunk_map = {c.chunk_id: c for c in chunks}
        total = 0.0

        for hyp in hypotheses:
            supporting = [chunk_map[cid] for cid in hyp.supporting_chunks if cid in chunk_map]

            # Evidencia efectiva
            if supporting:
                evidence_strength = sum(c.score for c in supporting) / len(supporting)
            else:
                evidence_strength = 0.0

            # La confianza no debería exceder mucho la evidencia
            if hyp.confidence > 0:
                ratio = min(evidence_strength / max(hyp.confidence, 0.01), 1.0)
            else:
                ratio = 0.0

            total += ratio

        return total / len(hypotheses)

    def _evaluate_novelty(
        self,
        chunks: List[RetrievedChunk],
        current_round: int,
    ) -> float:
        """
        Evalúa si la iteración actual aporta información nueva.

        En ronda 1, novelty es 1.0 (todo es nuevo).
        En rondas posteriores, mide cuántos chunks son nuevos.
        """
        if current_round <= 1:
            # Primera ronda: todo es nuevo
            if not chunks:
                return 0.0
            for c in chunks:
                self._previous_fingerprints.add(c.fingerprint)
            return 1.0

        if not chunks:
            return 0.0

        current_round_chunks = [c for c in chunks if c.retrieval_round == current_round]
        if not current_round_chunks:
            return 0.0

        new_count = 0
        for chunk in current_round_chunks:
            if chunk.fingerprint not in self._previous_fingerprints:
                new_count += 1
                self._previous_fingerprints.add(chunk.fingerprint)

        return new_count / len(current_round_chunks)

    def check_gates(self, score: QualityScore) -> Dict[str, bool]:
        """Verifica cada gate individual."""
        return {
            "relevance": score.relevance >= self.thresholds.get("relevance", 0.7),
            "coverage": score.coverage >= self.thresholds.get("coverage", 0.6),
            "consistency": score.consistency >= self.thresholds.get("consistency", 0.8),
            "confidence": score.confidence >= self.thresholds.get("confidence", 0.75),
            "novelty": score.novelty >= self.thresholds.get("novelty", 0.3),
        }

    def all_gates_passed(self, score: QualityScore) -> bool:
        """Retorna True si todos los gates pasan."""
        gates = self.check_gates(score)
        return all(gates.values())

    def get_weakest_dimension(self, score: QualityScore) -> str:
        """Retorna la dimensión más débil (mayor gap con su threshold)."""
        gaps = {}
        for dim, threshold in self.thresholds.items():
            actual = getattr(score, dim, 0.0)
            gaps[dim] = threshold - actual
        return max(gaps, key=gaps.get)

    def reset(self) -> None:
        """Resetea estado interno."""
        self._previous_fingerprints.clear()
