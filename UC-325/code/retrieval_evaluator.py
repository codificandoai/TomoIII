"""
UC-325 — Evaluador de Retrieval para el Motor de Razonamiento Autorreflexivo.

Evalúa la calidad de los chunks recuperados antes de usarlos en hipótesis.
Reemplaza la ausencia de evaluación en brain_memory_pipeline._retrieve_relevant_memories().

Funciones principales:
1. Evaluar relevancia individual de cada chunk al query.
2. Evaluar cobertura colectiva de los chunks.
3. Detectar chunks redundantes o contradictorios.
4. Decidir si es necesario re-recuperar con queries refinados.
"""

from typing import List, Dict, Optional, Tuple, Set
import hashlib
import math

from reasoning_models import (
    RetrievedChunk,
    ReasoningState,
    KnowledgeGap,
)


class RetrievalEvaluator:
    """
    Evalúa la calidad del retrieval y decide si re-recuperar.

    Opera de forma determinista usando heurísticas de overlap textual,
    distribución de scores, y análisis de cobertura temática.
    """

    def __init__(
        self,
        min_relevance: float = 0.3,
        min_coverage: float = 0.5,
        redundancy_threshold: float = 0.85,
    ):
        self.min_relevance = min_relevance
        self.min_coverage = min_coverage
        self.redundancy_threshold = redundancy_threshold

    def evaluate_chunks(
        self,
        query: str,
        chunks: List[RetrievedChunk],
    ) -> Dict[str, float]:
        """
        Evalúa la calidad colectiva de un conjunto de chunks.

        Retorna un diccionario con métricas:
        - avg_relevance: relevancia promedio al query.
        - score_distribution: varianza de scores (baja = homogéneo).
        - coverage: estimación de cobertura temática.
        - redundancy: ratio de chunks redundantes.
        - quality_score: score compuesto 0-1.
        """
        if not chunks:
            return {
                "avg_relevance": 0.0,
                "score_distribution": 0.0,
                "coverage": 0.0,
                "redundancy": 0.0,
                "quality_score": 0.0,
                "should_requery": True,
            }

        # Relevancia promedio
        relevances = [self._compute_relevance(query, c) for c in chunks]
        avg_relevance = sum(relevances) / len(relevances)

        # Actualizar relevance_score en cada chunk
        for chunk, rel in zip(chunks, relevances):
            chunk.relevance_score = rel

        # Distribución de scores
        scores = [c.score for c in chunks]
        mean_score = sum(scores) / len(scores)
        variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
        score_distribution = math.sqrt(variance)

        # Cobertura temática
        coverage = self._estimate_coverage(query, chunks)

        # Redundancia
        redundancy = self._compute_redundancy(chunks)

        # Score compuesto
        quality_score = (
            0.35 * avg_relevance
            + 0.25 * coverage
            + 0.20 * mean_score
            + 0.20 * (1.0 - redundancy)
        )

        should_requery = (
            avg_relevance < self.min_relevance
            or coverage < self.min_coverage
            or quality_score < 0.4
        )

        return {
            "avg_relevance": round(avg_relevance, 4),
            "score_distribution": round(score_distribution, 4),
            "coverage": round(coverage, 4),
            "redundancy": round(redundancy, 4),
            "quality_score": round(quality_score, 4),
            "should_requery": should_requery,
        }

    def filter_relevant(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        min_score: Optional[float] = None,
    ) -> List[RetrievedChunk]:
        """
        Filtra chunks por relevancia mínima al query.

        Retorna solo los chunks con relevancia >= min_score.
        """
        threshold = min_score if min_score is not None else self.min_relevance

        result = []
        for chunk in chunks:
            rel = self._compute_relevance(query, chunk)
            chunk.relevance_score = rel
            if rel >= threshold:
                result.append(chunk)

        return result

    def detect_contradictions(
        self,
        chunks: List[RetrievedChunk],
    ) -> List[Tuple[str, str, str]]:
        """
        Detecta pares de chunks que se contradicen.

        Retorna lista de (chunk_id_a, chunk_id_b, descripción).
        """
        contradictions = []
        negation_words = {
            "no", "not", "never", "sin", "ningún", "ninguno", "tampoco",
            "nunca", "jamás", "doesn't", "don't", "isn't", "aren't",
            "won't", "can't", "cannot",
        }

        for i, c1 in enumerate(chunks):
            c1_words = set(c1.content.lower().split())
            c1_has_neg = bool(c1_words & negation_words)

            for c2 in chunks[i + 1:]:
                c2_words = set(c2.content.lower().split())
                c2_has_neg = bool(c2_words & negation_words)

                # Mismo tema pero una tiene negación y otra no
                stop_words = {
                    "el", "la", "los", "las", "de", "en", "un", "una",
                    "que", "es", "se", "con", "por", "para", "su", "al",
                    "the", "a", "an", "is", "of", "in", "to", "and",
                }
                meaningful_1 = c1_words - stop_words - negation_words
                meaningful_2 = c2_words - stop_words - negation_words

                if not meaningful_1 or not meaningful_2:
                    continue

                overlap = len(meaningful_1 & meaningful_2) / min(
                    len(meaningful_1), len(meaningful_2)
                )

                if overlap > 0.4 and c1_has_neg != c2_has_neg:
                    contradictions.append((
                        c1.chunk_id,
                        c2.chunk_id,
                        f"Potential contradiction: same topic, opposite polarity",
                    ))

        return contradictions

    def deduplicate(
        self,
        new_chunks: List[RetrievedChunk],
        existing_chunks: List[RetrievedChunk],
        threshold: Optional[float] = None,
    ) -> List[RetrievedChunk]:
        """
        Elimina chunks duplicados semánticos.

        Compara fingerprints y overlap textual.
        """
        dedup_threshold = threshold if threshold is not None else self.redundancy_threshold
        existing_fingerprints = {c.fingerprint for c in existing_chunks}
        existing_texts = [c.content.lower() for c in existing_chunks]

        unique = []
        for chunk in new_chunks:
            # Exacto por fingerprint
            if chunk.fingerprint in existing_fingerprints:
                continue

            # Overlap textual
            is_dup = False
            chunk_words = set(chunk.content.lower().split())

            for existing_text in existing_texts:
                existing_words = set(existing_text.split())
                if not chunk_words or not existing_words:
                    continue

                intersection = len(chunk_words & existing_words)
                union = len(chunk_words | existing_words)
                jaccard = intersection / union if union > 0 else 0.0

                if jaccard >= dedup_threshold:
                    is_dup = True
                    break

            if not is_dup:
                unique.append(chunk)
                existing_fingerprints.add(chunk.fingerprint)
                existing_texts.append(chunk.content.lower())

        return unique

    def suggest_requery_strategy(
        self,
        evaluation: Dict[str, float],
        state: ReasoningState,
    ) -> Dict[str, any]:
        """
        Sugiere estrategia de re-query basada en la evaluación.

        Retorna:
        - strategy: "expand" | "specialize" | "verify" | "generalize" | "none"
        - reason: explicación.
        - priority_gaps: gaps prioritarios a cubrir.
        """
        if not evaluation.get("should_requery", False):
            return {"strategy": "none", "reason": "Quality sufficient", "priority_gaps": []}

        avg_rel = evaluation.get("avg_relevance", 0)
        coverage = evaluation.get("coverage", 0)
        redundancy = evaluation.get("redundancy", 0)

        if avg_rel < 0.3:
            return {
                "strategy": "generalize",
                "reason": f"Very low relevance ({avg_rel:.2f}). Try broader queries.",
                "priority_gaps": [g.to_dict() for g in state.unfilled_gaps[:3]],
            }

        if coverage < 0.4:
            return {
                "strategy": "expand",
                "reason": f"Low coverage ({coverage:.2f}). Expand to cover more aspects.",
                "priority_gaps": [g.to_dict() for g in state.unfilled_gaps[:3]],
            }

        if redundancy > 0.6:
            return {
                "strategy": "specialize",
                "reason": f"High redundancy ({redundancy:.2f}). Try more specific queries.",
                "priority_gaps": [g.to_dict() for g in state.unfilled_gaps[:3]],
            }

        return {
            "strategy": "verify",
            "reason": "Moderate quality. Verify weak hypotheses.",
            "priority_gaps": [g.to_dict() for g in state.unfilled_gaps[:3]],
        }

    def _compute_relevance(self, query: str, chunk: RetrievedChunk) -> float:
        """Calcula relevancia de un chunk al query usando Jaccard ponderado."""
        if not query or not chunk.content:
            return 0.0

        stop_words = {
            "el", "la", "los", "las", "de", "del", "en", "un", "una",
            "que", "es", "se", "con", "por", "para", "su", "al", "y",
            "the", "a", "an", "is", "are", "of", "in", "to", "and", "or",
        }

        query_words = set(query.lower().split()) - stop_words
        chunk_words = set(chunk.content.lower().split()) - stop_words

        if not query_words:
            return 0.0

        intersection = len(query_words & chunk_words)
        # Weighted: how many query words appear in the chunk
        recall = intersection / len(query_words)
        # Also consider chunk retrieval score
        combined = recall * 0.6 + min(chunk.score, 1.0) * 0.4

        return min(combined, 1.0)

    def _estimate_coverage(self, query: str, chunks: List[RetrievedChunk]) -> float:
        """Estima cobertura temática basada en diversidad de contenido."""
        if not chunks:
            return 0.0

        # Unique words across all chunks
        all_words: Set[str] = set()
        per_chunk_words: List[Set[str]] = []

        for chunk in chunks:
            words = set(chunk.content.lower().split())
            per_chunk_words.append(words)
            all_words.update(words)

        if not all_words:
            return 0.0

        # Coverage = ratio of unique content across chunks
        if len(chunks) == 1:
            return 0.5  # Single chunk = partial coverage

        # Measure diversity: average pairwise Jaccard distance
        total_distance = 0.0
        pairs = 0

        for i, w1 in enumerate(per_chunk_words):
            for w2 in per_chunk_words[i + 1:]:
                if not w1 or not w2:
                    continue
                intersection = len(w1 & w2)
                union = len(w1 | w2)
                jaccard = intersection / union if union > 0 else 0.0
                total_distance += (1.0 - jaccard)
                pairs += 1

        avg_distance = total_distance / pairs if pairs > 0 else 0.0

        # High distance = diverse content = good coverage
        return min(avg_distance, 1.0)

    def _compute_redundancy(self, chunks: List[RetrievedChunk]) -> float:
        """Calcula ratio de redundancia entre chunks."""
        if len(chunks) <= 1:
            return 0.0

        redundant = 0
        total_pairs = 0

        fingerprints = [c.fingerprint for c in chunks]
        for i, fp1 in enumerate(fingerprints):
            for fp2 in fingerprints[i + 1:]:
                total_pairs += 1
                if fp1 == fp2:
                    redundant += 1

        # Also check textual overlap
        for i, c1 in enumerate(chunks):
            c1_words = set(c1.content.lower().split())
            for c2 in chunks[i + 1:]:
                c2_words = set(c2.content.lower().split())
                if not c1_words or not c2_words:
                    continue
                intersection = len(c1_words & c2_words)
                union = len(c1_words | c2_words)
                jaccard = intersection / union if union > 0 else 0.0
                if jaccard >= self.redundancy_threshold:
                    redundant += 1

        return redundant / total_pairs if total_pairs > 0 else 0.0

    def reset(self) -> None:
        """Resetea estado interno."""
        pass
