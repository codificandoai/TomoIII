"""QualityEvaluator — Evaluación multi-criterio para UC-276.

Evalúa la calidad del output generado usando heurísticas de dominio:
- clarity: longitud de oraciones, vocabulario
- conciseness: ratio output/input
- completeness: cobertura de conceptos clave
- accuracy: mejora progresiva con iteraciones
- coherence: conectores lógicos y estructura

Inspirado en:
- hankbesser/recursive-agents: critique phase multi-dimensión.
- kayba-ai/recursive-improve: evaluate step.
"""
from __future__ import annotations

import hashlib
from typing import Dict, List, Optional

from models import QualityCriteria, QualityReport, RecursiveVersion


class QualityEvaluator:
    """Evalúa la calidad de una versión contra criterios ponderados."""

    def __init__(self, criteria: List[QualityCriteria]) -> None:
        self.criteria = criteria

    def evaluate(self, version: RecursiveVersion,
                 original_input: str,
                 task_description: str = "") -> QualityReport:
        """Evalúa calidad de una versión usando heurísticas multi-criterio."""
        scores = self._compute_scores(version, original_input)
        return QualityReport.from_scores(
            version_id=version.version_id,
            criteria=self.criteria,
            scores=scores,
        )

    def _compute_scores(self, version: RecursiveVersion,
                        original_input: str) -> Dict[str, float]:
        """Computa scores por criterio con heurísticas deterministas."""
        scores: Dict[str, float] = {}
        content = version.content
        content_len = len(content)

        for c in self.criteria:
            if c.name == "clarity":
                scores[c.name] = self._score_clarity(content)
            elif c.name == "conciseness":
                scores[c.name] = self._score_conciseness(content, original_input)
            elif c.name == "completeness":
                scores[c.name] = self._score_completeness(content, original_input)
            elif c.name == "accuracy":
                scores[c.name] = self._score_accuracy(content, version.iteration)
            elif c.name == "coherence":
                scores[c.name] = self._score_coherence(content)
            else:
                # Default: mejora progresiva basada en iteración
                base = 0.5 + version.iteration * 0.1
                seed = int(hashlib.md5((content[:50] + c.name).encode()).hexdigest()[:4], 16)
                jitter = (seed % 10) / 100.0
                scores[c.name] = min(1.0, base + jitter)

        return scores

    @staticmethod
    def _score_clarity(content: str) -> float:
        """Heurística: oraciones cortas → mayor claridad."""
        sentences = [s.strip() for s in content.split(".") if s.strip()]
        if not sentences:
            return 0.3
        avg_len = sum(len(s) for s in sentences) / len(sentences)
        # Oraciones de ~60 chars son óptimas
        score = max(0.3, min(1.0, 1.0 - abs(avg_len - 60) / 200.0))
        return round(score, 4)

    @staticmethod
    def _score_conciseness(content: str, original_input: str) -> float:
        """Heurística: ratio output/input ideal 0.3-0.7."""
        input_len = max(len(original_input), 1)
        ratio = len(content) / input_len
        if 0.3 <= ratio <= 0.7:
            return 0.9
        elif ratio < 0.3:
            return max(0.4, 0.6 + ratio)
        else:
            return max(0.3, 1.0 - (ratio - 0.7) * 0.5)

    @staticmethod
    def _score_completeness(content: str, original_input: str) -> float:
        """Heurística: cobertura de palabras clave del input."""
        input_words = set(w.lower() for w in original_input.split() if len(w) > 3)
        if not input_words:
            return 0.7
        output_words = set(w.lower() for w in content.split() if len(w) > 3)
        overlap = len(input_words & output_words) / len(input_words)
        return round(min(1.0, overlap * 1.5), 4)

    @staticmethod
    def _score_accuracy(content: str, iteration: int) -> float:
        """Heurística: mejora progresiva con iteraciones (simula LLM refinement)."""
        base = 0.55 + iteration * 0.08
        seed = int(hashlib.md5(content[:30].encode()).hexdigest()[:4], 16)
        jitter = (seed % 8) / 100.0
        return round(min(1.0, base + jitter), 4)

    @staticmethod
    def _score_coherence(content: str) -> float:
        """Heurística: presencia de conectores lógicos."""
        connectors = [
            "por lo tanto", "además", "sin embargo", "en conclusión",
            "primero", "segundo", "finalmente", "asimismo",
            "en resumen", "dado que", "no obstante", "por ejemplo",
            "therefore", "moreover", "however", "furthermore",
            "in conclusion", "first", "finally", "for example",
        ]
        lower = content.lower()
        found = sum(1 for c in connectors if c in lower)
        return round(min(1.0, 0.45 + found * 0.1), 4)
