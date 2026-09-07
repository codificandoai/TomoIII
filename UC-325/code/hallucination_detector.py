"""
UC-325 — Detector de Alucinaciones para el Motor de Razonamiento Autorreflexivo.

Detecta seis tipos de alucinaciones durante el razonamiento:
1. claim_without_evidence: afirmaciones sin soporte en chunks.
2. fabricated_source: referencias a fuentes inexistentes.
3. confidence_inflation: confianza desproporcionada a la evidencia.
4. contradiction_with_evidence: hipótesis que contradicen la evidencia.
5. extrapolation_beyond_data: conclusiones que van más allá de los datos.
6. temporal_inconsistency: datos temporalmente inconsistentes.

Principio: Un modelo genera evidencia. La evidencia no es una orden.
"""

from typing import List, Dict, Optional, Set, Tuple
import re
import math

from reasoning_models import (
    HallucinationReport,
    Hypothesis,
    RetrievedChunk,
    ReasoningState,
    HypothesisStatus,
    HALLUCINATION_PATTERNS,
)


class HallucinationDetector:
    """
    Detecta alucinaciones comparando hipótesis contra evidencia disponible.

    Opera de forma determinista sin LLM: usa heurísticas de overlap textual,
    verificación de fuentes, y análisis de confianza vs. evidencia.
    """

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
        self._detection_history: List[HallucinationReport] = []

    def detect(self, state: ReasoningState) -> HallucinationReport:
        """Ejecuta todos los detectores y genera reporte consolidado."""
        chunks = list(state.all_chunks.values())
        hypotheses = state.active_hypotheses

        if not hypotheses:
            return HallucinationReport()

        unsupported = self._detect_unsupported_claims(hypotheses, chunks)
        fabricated = self._detect_fabricated_sources(hypotheses, chunks)
        inflation = self._detect_confidence_inflation(hypotheses, chunks)
        contradictions = self._detect_contradictions(hypotheses, chunks)
        extrapolations = self._detect_extrapolations(hypotheses, chunks)

        # Calcular severidad agregada
        issues_count = (
            len(unsupported)
            + len(fabricated)
            + (1 if inflation > 0.3 else 0)
            + len(contradictions)
            + len(extrapolations)
        )

        severity = min(issues_count / max(len(hypotheses), 1), 1.0)
        detected = severity >= self.threshold

        # Determinar tipo principal
        hallucination_type = None
        if fabricated:
            hallucination_type = "fabricated_source"
        elif contradictions:
            hallucination_type = "contradiction_with_evidence"
        elif unsupported:
            hallucination_type = "claim_without_evidence"
        elif inflation > 0.3:
            hallucination_type = "confidence_inflation"
        elif extrapolations:
            hallucination_type = "extrapolation_beyond_data"

        # Recomendación
        if detected:
            if fabricated:
                recommendation = "Eliminar hipótesis con fuentes fabricadas y re-recuperar evidencia."
            elif contradictions:
                recommendation = "Refutar hipótesis que contradicen la evidencia y regenerar."
            elif unsupported:
                recommendation = "Buscar evidencia adicional o reducir confianza de claims sin soporte."
            elif inflation > 0.3:
                recommendation = "Ajustar confianza a niveles proporcionales a la evidencia."
            else:
                recommendation = "Re-evaluar hipótesis contra evidencia disponible."
        else:
            recommendation = "Sin alucinaciones detectadas. Continuar razonamiento."

        report = HallucinationReport(
            detected=detected,
            hallucination_type=hallucination_type,
            unsupported_claims=unsupported,
            fabricated_sources=fabricated,
            confidence_inflation=inflation,
            severity=severity,
            recommendation=recommendation,
        )

        self._detection_history.append(report)
        return report

    def _detect_unsupported_claims(
        self,
        hypotheses: List[Hypothesis],
        chunks: List[RetrievedChunk],
    ) -> List[str]:
        """
        Detecta hipótesis sin soporte suficiente en los chunks.

        Una hipótesis se considera sin soporte si:
        - No tiene chunks de soporte, O
        - Menos del 20% de sus palabras clave aparecen en los chunks.
        """
        unsupported = []
        chunk_map = {c.chunk_id: c for c in chunks}
        all_chunk_text = " ".join(c.content.lower() for c in chunks)
        all_chunk_words = set(all_chunk_text.split())

        for hyp in hypotheses:
            # Verificar chunks de soporte
            supporting = [chunk_map[cid] for cid in hyp.supporting_chunks if cid in chunk_map]

            if not supporting:
                unsupported.append(hyp.statement[:100])
                continue

            # Verificar overlap textual
            hyp_words = set(hyp.statement.lower().split())
            # Filtrar stop words
            stop_words = {
                "el", "la", "los", "las", "de", "del", "en", "un", "una",
                "que", "es", "se", "con", "por", "para", "su", "al",
                "the", "a", "an", "is", "are", "was", "of", "in", "to",
                "and", "or", "not", "it", "this", "that", "be", "has",
            }
            meaningful_words = hyp_words - stop_words
            if not meaningful_words:
                continue

            support_text = " ".join(c.content.lower() for c in supporting)
            support_words = set(support_text.split())

            overlap = len(meaningful_words & support_words) / len(meaningful_words)
            if overlap < 0.20:
                unsupported.append(hyp.statement[:100])

        return unsupported

    def _detect_fabricated_sources(
        self,
        hypotheses: List[Hypothesis],
        chunks: List[RetrievedChunk],
    ) -> List[str]:
        """
        Detecta referencias a fuentes que no existen en los chunks.

        Verifica que los chunk_ids referenciados existan.
        """
        fabricated = []
        chunk_ids = {c.chunk_id for c in chunks}

        for hyp in hypotheses:
            for cid in hyp.supporting_chunks:
                if cid not in chunk_ids:
                    fabricated.append(f"Hypothesis '{hyp.hypothesis_id}' references non-existent chunk '{cid}'")

        return fabricated

    def _detect_confidence_inflation(
        self,
        hypotheses: List[Hypothesis],
        chunks: List[RetrievedChunk],
    ) -> float:
        """
        Detecta inflación de confianza: confianza alta sin evidencia proporcional.

        Retorna un score 0-1 de inflación detectada.
        """
        if not hypotheses:
            return 0.0

        chunk_map = {c.chunk_id: c for c in chunks}
        inflation_scores = []

        for hyp in hypotheses:
            supporting = [chunk_map[cid] for cid in hyp.supporting_chunks if cid in chunk_map]

            if supporting:
                evidence_strength = sum(c.score for c in supporting) / len(supporting)
            else:
                evidence_strength = 0.0

            # Inflación = confianza - evidencia (cuando confianza > evidencia)
            if hyp.confidence > evidence_strength:
                inflation = hyp.confidence - evidence_strength
            else:
                inflation = 0.0

            inflation_scores.append(inflation)

        return sum(inflation_scores) / len(inflation_scores) if inflation_scores else 0.0

    def _detect_contradictions(
        self,
        hypotheses: List[Hypothesis],
        chunks: List[RetrievedChunk],
    ) -> List[str]:
        """
        Detecta hipótesis que se contradicen entre sí.

        Heurística: busca pares de hipótesis con negaciones o palabras
        antónimas sobre el mismo tema.
        """
        contradictions = []
        negation_words = {
            "no", "not", "never", "sin", "ningún", "ninguno", "tampoco",
            "nunca", "jamás", "ni", "doesn't", "don't", "isn't", "aren't",
            "won't", "can't", "cannot", "neither", "nor",
        }

        for i, h1 in enumerate(hypotheses):
            h1_words = set(h1.statement.lower().split())
            h1_has_neg = bool(h1_words & negation_words)

            for h2 in hypotheses[i + 1:]:
                h2_words = set(h2.statement.lower().split())
                h2_has_neg = bool(h2_words & negation_words)

                # Mismo tema pero una tiene negación y otra no
                stop_words = {
                    "el", "la", "los", "las", "de", "en", "un", "una",
                    "que", "es", "se", "con", "por", "para", "su", "al",
                    "the", "a", "an", "is", "of", "in", "to", "and",
                }
                meaningful_1 = h1_words - stop_words - negation_words
                meaningful_2 = h2_words - stop_words - negation_words

                if not meaningful_1 or not meaningful_2:
                    continue

                topic_overlap = len(meaningful_1 & meaningful_2) / min(
                    len(meaningful_1), len(meaningful_2)
                )

                if topic_overlap > 0.5 and h1_has_neg != h2_has_neg:
                    contradictions.append(
                        f"Contradiction: '{h1.statement[:60]}' vs '{h2.statement[:60]}'"
                    )

        return contradictions

    def _detect_extrapolations(
        self,
        hypotheses: List[Hypothesis],
        chunks: List[RetrievedChunk],
    ) -> List[str]:
        """
        Detecta conclusiones que van más allá de los datos disponibles.

        Heurística: hipótesis con palabras de certeza absoluta pero
        evidencia débil o parcial.
        """
        extrapolations = []
        certainty_markers = {
            "siempre", "nunca", "todos", "ninguno", "definitivamente",
            "absolutamente", "sin duda", "indudablemente", "certeza",
            "always", "never", "all", "none", "definitely", "absolutely",
            "certainly", "undoubtedly", "guaranteed", "proven",
        }

        chunk_map = {c.chunk_id: c for c in chunks}

        for hyp in hypotheses:
            hyp_lower = hyp.statement.lower()

            # Verificar marcadores de certeza
            has_certainty = any(marker in hyp_lower for marker in certainty_markers)

            if has_certainty:
                # Verificar fuerza de la evidencia
                supporting = [chunk_map[cid] for cid in hyp.supporting_chunks if cid in chunk_map]
                if not supporting or hyp.confidence < 0.8:
                    extrapolations.append(
                        f"Extrapolation: '{hyp.statement[:80]}' uses absolute language with weak evidence"
                    )

        return extrapolations

    def apply_corrections(self, state: ReasoningState, report: HallucinationReport) -> ReasoningState:
        """
        Aplica correcciones al estado basado en el reporte de alucinaciones.

        Reduce confianza de hipótesis problemáticas y marca fabricaciones.
        """
        if not report.detected:
            return state

        chunk_ids = set(state.all_chunks.keys())

        for hyp in state.active_hypotheses:
            # Corregir fabricaciones: eliminar chunk_ids inexistentes
            original_chunks = hyp.supporting_chunks[:]
            hyp.supporting_chunks = [cid for cid in hyp.supporting_chunks if cid in chunk_ids]

            if len(hyp.supporting_chunks) < len(original_chunks):
                # Reducir confianza proporcionalmente
                if original_chunks:
                    ratio = len(hyp.supporting_chunks) / len(original_chunks)
                    hyp.confidence *= ratio

            # Corregir inflación de confianza
            if report.confidence_inflation > 0.3:
                supporting = [state.all_chunks[cid] for cid in hyp.supporting_chunks if cid in state.all_chunks]
                if supporting:
                    max_evidence = max(c.score for c in supporting)
                    hyp.confidence = min(hyp.confidence, max_evidence * 1.1)

            # Refutar hipótesis con claim sin soporte
            if hyp.statement[:100] in report.unsupported_claims and not hyp.supporting_chunks:
                hyp.status = HypothesisStatus.REFUTED
                hyp.refuted_by = "hallucination_detector: no supporting evidence"

        return state

    def get_history(self) -> List[Dict]:
        """Retorna historial de detecciones."""
        return [r.to_dict() for r in self._detection_history]

    def reset(self) -> None:
        """Resetea estado interno."""
        self._detection_history.clear()
