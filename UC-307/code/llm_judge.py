"""Simulador del "LLM Juez" para el Nivel 2 de evaluación de UC-307.

En producción este módulo puede sustituirse por una llamada real a un modelo
(OpenAI GPT-4, Claude, etc.) sin alterar la interfaz pública.
"""
from __future__ import annotations

import random
import re
import time
from typing import Dict, Optional


class LLMJudge:
    """Juez evaluador de calidad de resultados de agentes autónomos."""

    RUBRIC: Dict[str, float] = {
        "relevance": 0.40,
        "coherence": 0.30,
        "completeness": 0.20,
        "correctness": 0.10,
    }

    def __init__(self, latency_seconds: float = 0.05):
        self.latency_seconds = latency_seconds

    def evaluate(
        self,
        task_description: str,
        result_text: str,
        expected_outcome: Optional[str] = None,
        rubric: Optional[Dict[str, float]] = None,
    ) -> float:
        """Devuelve una puntuación de calidad entre 1.0 y 5.0.

        El simulador usa una heurística determinista basada en:
        - Longitud razonable del resultado (ni vacío ni excesivo).
        - Presencia de términos relevantes extraídos de la descripción.
        - Penalización por palabras de error/fracaso.
        """
        if rubric is None:
            rubric = self.RUBRIC

        time.sleep(self.latency_seconds)

        text = result_text.strip().lower()
        desc = task_description.lower()

        if not text:
            return 1.0

        # Tokens relevantes de la descripción (palabras > 3 caracteres)
        desc_terms = set(re.findall(r"[a-záéíóúñ]{4,}", desc))
        matches = sum(1 for term in desc_terms if term in text)
        relevance = min(1.0, matches / max(1, len(desc_terms) * 0.4))

        # Coherence: castigo por errores comunes
        error_terms = {"error", "fail", "timeout", "exception", "no se pudo", "unable"}
        error_hits = sum(1 for term in error_terms if term in text)
        coherence = max(0.0, 1.0 - error_hits * 0.25)

        # Completeness: longitud relativa
        words = len(re.findall(r"\w+", text))
        completeness = min(1.0, words / 30.0) if words < 30 else min(1.0, 60.0 / words)

        # Correctness: boost si coincide con expected_outcome
        correctness = 0.5
        if expected_outcome:
            expected_terms = set(re.findall(r"\w+", expected_outcome.lower()))
            if expected_terms:
                overlap = len(expected_terms & set(re.findall(r"\w+", text))) / len(expected_terms)
                correctness = 0.5 + 0.5 * overlap

        weighted = (
            rubric["relevance"] * relevance
            + rubric["coherence"] * coherence
            + rubric["completeness"] * completeness
            + rubric["correctness"] * correctness
        )

        # Mapear 0..1 a escala 1..5, añadir pequeña variación realista
        score = 1.0 + 4.0 * weighted
        score = min(5.0, max(1.0, score + random.uniform(-0.1, 0.1)))
        return round(score, 1)

    def build_explanation(self, task_description: str, result_text: str, score: float) -> str:
        """Construye un breve dictamen del juez (útil para logs y dashboards)."""
        return (
            f"El LLM Juez calificó el resultado de '{task_description[:40]}...' "
            f"con {score}/5.0 según los criterios de relevancia, coherencia, "
            f"completitud y corrección."
        )
