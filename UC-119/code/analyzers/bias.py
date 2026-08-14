"""Detección de sesgos (género, raza, edad, religión)."""

from dataclasses import dataclass, field
from typing import List

from config import BIAS_TERMS, CONFIG


@dataclass
class BiasMetrics:
    """Métricas de sesgo detectado."""
    gender_bias_score: float
    racial_bias_score: float
    age_bias_score: float
    religious_bias_score: float
    overall_bias_score: float
    biased_terms: List[str] = field(default_factory=list)


class BiasDetector:
    """Detecta sesgos en el texto."""

    def __init__(self, bias_terms=None):
        self.bias_terms = bias_terms or BIAS_TERMS

    def analyze(self, text: str) -> BiasMetrics:
        """Analiza sesgos en el texto."""
        if not text:
            return BiasMetrics(0.0, 0.0, 0.0, 0.0, 0.0, [])

        text_lower = text.lower()
        words = text_lower.split()

        male_count = sum(1 for term in self.bias_terms['gender']['male'] if term in words)
        female_count = sum(1 for term in self.bias_terms['gender']['female'] if term in words)
        total_gender = male_count + female_count
        gender_bias = abs(male_count - female_count) / total_gender if total_gender > 0 else 0.0

        racial_count = sum(1 for term in self.bias_terms['racial'] if term in text_lower)
        age_count = sum(1 for term in self.bias_terms['age'] if term in text_lower)
        religious_count = sum(1 for term in self.bias_terms['religious'] if term in text_lower)

        racial_bias = min(racial_count / 10, 1.0)
        age_bias = min(age_count / 10, 1.0)
        religious_bias = min(religious_count / 10, 1.0)

        overall_bias = (gender_bias + racial_bias + age_bias + religious_bias) / 4

        biased_terms = []
        if gender_bias > 0.5:
            biased_terms.append("gender_imbalance")
        if racial_bias > 0.3:
            biased_terms.append("racial_references")
        if age_bias > 0.3:
            biased_terms.append("age_references")
        if religious_bias > 0.3:
            biased_terms.append("religious_references")

        return BiasMetrics(
            gender_bias_score=round(gender_bias, 4),
            racial_bias_score=round(racial_bias, 4),
            age_bias_score=round(age_bias, 4),
            religious_bias_score=round(religious_bias, 4),
            overall_bias_score=round(overall_bias, 4),
            biased_terms=biased_terms,
        )
