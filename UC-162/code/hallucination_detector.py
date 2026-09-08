"""
UC-162 — Detector de hallucination.

Valida coherencia lógica de las narrativas generadas por el LLM de UC-315.
UC-087 protege los modelos de transición (NeuralTransitionModel,
GPTransitionModel); UC-162 valida los outputs del LLM.

Detecta:
- Claims no soportados por los chunks recuperados (coverage).
- Contradicciones entre la respuesta y las fuentes.
- Entropía anormal en la respuesta (alta incertidumbre).
"""

import re
import math
from collections import Counter
from typing import Dict, List, Optional, Any

from models_162 import HallucinationReport, HallucinationSeverity, LLMOpsConfig


class HallucinationDetector:
    """Detecta hallucination en respuestas del LLM."""

    def __init__(self, config: Optional[LLMOpsConfig] = None):
        self.config = config or LLMOpsConfig()

    def detect(
        self,
        response: str,
        retrieved_chunks: List[str],
        trace_id: str = "",
    ) -> HallucinationReport:
        """
        Evalúa si la respuesta es una hallucination.

        Métricas:
        - coverage_score: qué fracción de la respuesta está soportada por chunks.
        - contradiction_score: presencia de afirmaciones contradictorias.
        - entropy_score: entropía de tokens (alta = menos confiable).
        """
        report = HallucinationReport(trace_id=trace_id)

        if not response:
            report.severity = HallucinationSeverity.HIGH.value
            report.is_hallucination = True
            report.unsupported_claims.append("Respuesta vacía")
            return report

        if not retrieved_chunks:
            report.coverage_score = 0.0
            report.severity = HallucinationSeverity.HIGH.value
            report.is_hallucination = True
            report.unsupported_claims.append(
                "Respuesta sin chunks recuperados de soporte"
            )
            return report

        # 1. Coverage: qué fracción de palabras de la respuesta aparecen en chunks
        report.coverage_score = self._compute_coverage(response, retrieved_chunks)

        # 2. Contradicción: negaciones o afirmaciones opuestas
        report.contradiction_score = self._compute_contradiction(
            response, retrieved_chunks
        )

        # 3. Entropía de tokens
        report.entropy_score = self._compute_entropy(response)

        # 4. Detectar claims no soportados
        report.unsupported_claims = self._find_unsupported_claims(
            response, retrieved_chunks
        )

        # 5. Determinar severidad
        report.severity = self._determine_severity(report)
        report.is_hallucination = report.severity in (
            HallucinationSeverity.HIGH.value,
            HallucinationSeverity.CRITICAL.value,
        )

        # 6. Flags de chunks sospechosos
        report.flagged_chunks = self._flag_suspicious_chunks(
            response, retrieved_chunks
        )

        return report

    def _compute_coverage(
        self, response: str, chunks: List[str]
    ) -> float:
        """Calcula qué fracción de tokens de la respuesta están en los chunks."""
        response_tokens = self._tokenize(response)
        if not response_tokens:
            return 0.0
        chunk_tokens = set()
        for c in chunks:
            chunk_tokens.update(self._tokenize(c))
        if not chunk_tokens:
            return 0.0
        covered = sum(1 for t in response_tokens if t in chunk_tokens)
        return round(covered / len(response_tokens), 4)

    def _compute_contradiction(
        self, response: str, chunks: List[str]
    ) -> float:
        """Detecta presencia de indicadores de contradicción."""
        contradiction_markers = [
            r"\bno\b", r"\bnunca\b", r"\bnada\b", r"\bningún\b",
            r"\bimposible\b", r"\bfalso\b", r"\bincorrecto\b",
            r"\bnot\b", r"\bnever\b", r"\bfalse\b", r"\bwrong\b",
        ]
        response_lower = response.lower()
        chunk_text = " ".join(chunks).lower()

        response_contradictions = sum(
            1 for pattern in contradiction_markers
            if re.search(pattern, response_lower)
        )
        chunk_contradictions = sum(
            1 for pattern in contradiction_markers
            if re.search(pattern, chunk_text)
        )

        # Si la respuesta tiene más contradicciones que los chunks, sospechoso
        if response_contradictions == 0:
            return 0.0
        if chunk_contradictions == 0:
            return min(1.0, response_contradictions * 0.2)
        diff = abs(response_contradictions - chunk_contradictions)
        return round(min(1.0, diff * 0.15), 4)

    def _compute_entropy(self, text: str) -> float:
        """Calcula entropía de Shannon de los tokens. Alta = menos confiable."""
        tokens = self._tokenize(text)
        if not tokens:
            return 0.0
        counter = Counter(tokens)
        total = len(tokens)
        entropy = 0.0
        for count in counter.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)
        # Normalizar a 0-1 (máx entropy = log2(vocab_size))
        max_entropy = math.log2(len(counter)) if len(counter) > 1 else 1
        return round(entropy / max_entropy if max_entropy > 0 else 0, 4)

    def _find_unsupported_claims(
        self, response: str, chunks: List[str]
    ) -> List[str]:
        """Identifica frases de la respuesta no soportadas por los chunks."""
        sentences = re.split(r"[.!?]+", response)
        chunk_text = " ".join(chunks).lower()
        unsupported = []
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 10:
                continue
            sent_tokens = set(self._tokenize(sent.lower()))
            if not sent_tokens:
                continue
            chunk_tokens = set(self._tokenize(chunk_text))
            overlap = len(sent_tokens & chunk_tokens) / len(sent_tokens)
            if overlap < 0.3:
                unsupported.append(sent[:100])
        return unsupported

    def _flag_suspicious_chunks(
        self, response: str, chunks: List[str]
    ) -> List[str]:
        """Identifica chunks que no contribuyen a la respuesta."""
        response_tokens = set(self._tokenize(response.lower()))
        flagged = []
        for i, chunk in enumerate(chunks):
            chunk_tokens = set(self._tokenize(chunk.lower()))
            if not chunk_tokens:
                continue
            overlap = len(response_tokens & chunk_tokens) / len(chunk_tokens)
            if overlap < 0.1:
                flagged.append(f"chunk_{i}")
        return flagged

    def _determine_severity(
        self, report: HallucinationReport
    ) -> str:
        """Determina severidad basada en las métricas."""
        score = 0.0
        if report.coverage_score < self.config.hallucination_coverage_threshold:
            score += 0.4
        if report.contradiction_score > self.config.hallucination_contradiction_threshold:
            score += 0.3
        if report.entropy_score > self.config.hallucination_entropy_threshold:
            score += 0.2
        if len(report.unsupported_claims) > 3:
            score += 0.2

        if score >= 0.7:
            return HallucinationSeverity.CRITICAL.value
        elif score >= 0.5:
            return HallucinationSeverity.HIGH.value
        elif score >= 0.3:
            return HallucinationSeverity.MEDIUM.value
        elif score >= 0.1:
            return HallucinationSeverity.LOW.value
        return HallucinationSeverity.NONE.value

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenización simple por palabras."""
        return re.findall(r"\b\w+\b", text.lower())
