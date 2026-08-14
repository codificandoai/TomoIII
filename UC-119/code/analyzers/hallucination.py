"""Detección de alucinaciones (consistencia factual, auto-consistencia)."""

import logging
from dataclasses import dataclass

from config import CONFIG

logger = logging.getLogger(__name__)

_UNCERTAINTY_MARKERS = [
    'maybe', 'perhaps', 'i think', 'not sure', 'possibly',
    'quizás', 'quizas', 'tal vez', 'no estoy seguro',
]


@dataclass
class HallucinationMetrics:
    """Métricas de detección de alucinaciones."""
    factual_consistency_score: float
    self_consistency_score: float
    confidence_score: float
    contradiction_detected: bool
    hallucination_probability: float
    risk_level: str  # LOW, MEDIUM, HIGH


def _classify_risk(prob: float) -> str:
    t = CONFIG.thresholds
    if prob > t.hallucination_high:
        return "HIGH"
    if prob > t.hallucination_medium:
        return "MEDIUM"
    return "LOW"


class HallucinationDetector:
    """Detecta posibles alucinaciones en las respuestas del modelo.

    Con contexto disponible (RAG), utiliza un modelo de Inferencia de
    Lenguaje Natural (NLI) de forma perezosa para verificar si la respuesta
    contradice el contexto recuperado (`groundedness`). Sin contexto, o si
    el modelo no está disponible, recurre a heurísticas.
    """

    def __init__(self, use_nli: bool = None):
        self._use_nli = CONFIG.model.use_ml_models if use_nli is None else use_nli
        self._pipeline = None

    def _get_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        try:
            import torch
            from transformers import pipeline
            self._pipeline = pipeline(
                "text-classification",
                model="facebook/bart-large-mnli",
                device=0 if torch.cuda.is_available() else -1,
                return_all_scores=True,
            )
            logger.info("Modelo NLI para detección de alucinaciones cargado")
        except Exception as e:  # pragma: no cover
            logger.warning(f"No se pudo cargar modelo NLI, usando heurísticas: {e}")
            self._use_nli = False
        return self._pipeline

    def analyze(self, prompt: str, response: str, context: str = "") -> HallucinationMetrics:
        """Analiza posibles alucinaciones."""
        if self._use_nli and context:
            pipe = self._get_pipeline()
            if pipe is not None:
                return self._analyze_with_nli(response, context, pipe)
        return self._analyze_with_heuristics(prompt, response)

    def _analyze_with_nli(self, response: str, context: str, pipe) -> HallucinationMetrics:
        try:
            result = pipe(f"{context} </s></s> {response}")
            scores_by_label = {r['label'].lower(): r['score'] for r in result[0]}

            entailment_score = scores_by_label.get('entailment', 0.0)
            contradiction_score = scores_by_label.get('contradiction', 0.0)

            contradiction_detected = contradiction_score > 0.5
            hallucination_prob = contradiction_score

            return HallucinationMetrics(
                factual_consistency_score=round(entailment_score, 4),
                self_consistency_score=0.8,
                confidence_score=round(entailment_score, 4),
                contradiction_detected=contradiction_detected,
                hallucination_probability=round(hallucination_prob, 4),
                risk_level=_classify_risk(hallucination_prob),
            )
        except Exception as e:  # pragma: no cover
            logger.error(f"Error en análisis NLI: {e}")
            return self._analyze_with_heuristics("", response)

    def _analyze_with_heuristics(self, prompt: str, response: str) -> HallucinationMetrics:
        prompt_words = len(prompt.split()) if prompt else 0
        response_words = len(response.split()) if response else 0
        length_ratio = response_words / prompt_words if prompt_words > 0 else 0.0

        uncertainty_count = sum(
            1 for marker in _UNCERTAINTY_MARKERS if marker in response.lower()
        )

        words = response.lower().split()
        unique_words = set(words)
        repetition_ratio = 1 - (len(unique_words) / len(words)) if len(words) > 0 else 0.0

        hallucination_prob = 0.0
        if length_ratio > 5:
            hallucination_prob += 0.3
        if uncertainty_count > 2:
            hallucination_prob += 0.2
        if repetition_ratio > 0.5:
            hallucination_prob += 0.3
        hallucination_prob = min(hallucination_prob, 1.0)

        return HallucinationMetrics(
            factual_consistency_score=round(1 - hallucination_prob, 4),
            self_consistency_score=round(1 - repetition_ratio, 4),
            confidence_score=round(max(1 - uncertainty_count / 5, 0.0), 4),
            contradiction_detected=False,
            hallucination_probability=round(hallucination_prob, 4),
            risk_level=_classify_risk(hallucination_prob),
        )
