"""Detección de contenido tóxico o dañino."""

import logging
from dataclasses import dataclass, field
from typing import List

from config import TOXIC_TERMS, CONFIG

logger = logging.getLogger(__name__)


@dataclass
class ToxicityMetrics:
    """Métricas de toxicidad y contenido dañino."""
    toxicity_score: float
    severe_toxicity_score: float
    obscene_score: float
    threat_score: float
    insult_score: float
    identity_hate_score: float
    overall_risk: str  # LOW, MEDIUM, HIGH, CRITICAL
    flagged_terms: List[str] = field(default_factory=list)


def _classify_risk(score: float) -> str:
    t = CONFIG.thresholds
    if score > t.toxicity_critical:
        return "CRITICAL"
    if score > t.toxicity_high:
        return "HIGH"
    if score > t.toxicity_medium:
        return "MEDIUM"
    return "LOW"


class ToxicityDetector:
    """Detecta contenido tóxico y dañino.

    Usa heurísticas basadas en léxico por defecto. Si `use_ml_model=True`
    (o `CONFIG.model.use_ml_models`), intenta cargar `unitary/toxic-bert`
    de forma perezosa (lazy) para no penalizar el arranque ni los tests
    unitarios con descargas de modelos pesados.
    """

    def __init__(self, use_ml_model: bool = None, toxic_terms=None):
        self.toxic_terms = toxic_terms or TOXIC_TERMS
        self._use_ml_model = (
            CONFIG.model.use_ml_models if use_ml_model is None else use_ml_model
        )
        self._pipeline = None

    def _get_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        try:
            import torch
            from transformers import pipeline
            self._pipeline = pipeline(
                "text-classification",
                model="unitary/toxic-bert",
                device=0 if torch.cuda.is_available() else -1,
            )
            logger.info("Modelo de toxicidad cargado (unitary/toxic-bert)")
        except Exception as e:  # pragma: no cover - depende de infra externa
            logger.warning(f"No se pudo cargar modelo de toxicidad, usando heurísticas: {e}")
            self._use_ml_model = False
        return self._pipeline

    def analyze(self, text: str) -> ToxicityMetrics:
        """Analiza toxicidad en el texto."""
        if not text:
            return ToxicityMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "LOW", [])

        if self._use_ml_model:
            pipe = self._get_pipeline()
            if pipe is not None:
                return self._analyze_with_ml(text, pipe)

        return self._analyze_with_heuristics(text.lower())

    def _analyze_with_ml(self, text: str, pipe) -> ToxicityMetrics:
        try:
            results = pipe(text[:512])
            toxicity_score = 0.0
            for result in results:
                if result['label'].lower() == 'toxic':
                    toxicity_score = result['score']
            return ToxicityMetrics(
                toxicity_score=round(toxicity_score, 4),
                severe_toxicity_score=0.0,
                obscene_score=0.0,
                threat_score=0.0,
                insult_score=0.0,
                identity_hate_score=0.0,
                overall_risk=_classify_risk(toxicity_score),
                flagged_terms=[],
            )
        except Exception as e:  # pragma: no cover
            logger.error(f"Error en análisis ML de toxicidad: {e}")
            return self._analyze_with_heuristics(text.lower())

    def _analyze_with_heuristics(self, text_lower: str) -> ToxicityMetrics:
        flagged = []
        scores = {category: 0.0 for category in self.toxic_terms}

        for category, terms in self.toxic_terms.items():
            for term in terms:
                if term in text_lower:
                    scores[category] += 0.3
                    flagged.append(term)

        for key in scores:
            scores[key] = min(scores[key], 1.0)

        toxicity_score = max(scores.values()) if scores else 0.0

        return ToxicityMetrics(
            toxicity_score=round(toxicity_score, 4),
            severe_toxicity_score=round(scores.get('severe', 0.0), 4),
            obscene_score=round(scores.get('obscene', 0.0), 4),
            threat_score=round(scores.get('threat', 0.0), 4),
            insult_score=round(scores.get('insult', 0.0), 4),
            identity_hate_score=round(scores.get('identity_hate', 0.0), 4),
            overall_risk=_classify_risk(toxicity_score),
            flagged_terms=sorted(set(flagged)),
        )
