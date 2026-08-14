"""Analizador de diversidad léxica (TTR, entropía de Shannon, n-gramas)."""

from collections import Counter
from dataclasses import dataclass

import numpy as np


@dataclass
class DiversityMetrics:
    """Métricas de diversidad léxica."""
    unique_tokens_ratio: float
    type_token_ratio: float
    entropy: float
    ngram_diversity: float
    overall_score: float


def _simple_tokenize(text: str):
    """Tokenizador ligero sin dependencias externas (evita descargas NLTK)."""
    import re
    return re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑüÜ0-9]+", text.lower())


_STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'is', 'are', 'was', 'were', 'to',
    'of', 'in', 'on', 'for', 'with', 'as', 'by', 'at', 'it', 'this', 'that',
    'el', 'la', 'los', 'las', 'un', 'una', 'y', 'o', 'pero', 'es', 'son',
    'de', 'en', 'para', 'con', 'por', 'que', 'se', 'del', 'al',
}


def _ngrams(tokens, n):
    return list(zip(*[tokens[i:] for i in range(n)]))


class DiversityAnalyzer:
    """Analiza la diversidad léxica y semántica de textos."""

    def __init__(self, stop_words=None):
        self.stop_words = stop_words or _STOPWORDS

    def analyze(self, text: str) -> DiversityMetrics:
        """Analiza la diversidad de un texto."""
        if not text or len(text.strip()) == 0:
            return DiversityMetrics(0.0, 0.0, 0.0, 0.0, 0.0)

        tokens = _simple_tokenize(text)
        tokens = [t for t in tokens if t not in self.stop_words]

        if len(tokens) == 0:
            return DiversityMetrics(0.0, 0.0, 0.0, 0.0, 0.0)

        unique_tokens = set(tokens)
        unique_ratio = len(unique_tokens) / len(tokens)
        ttr = unique_ratio  # Type-Token Ratio == unique ratio para una sola muestra

        token_counts = Counter(tokens)
        total_tokens = len(tokens)
        probabilities = [count / total_tokens for count in token_counts.values()]
        entropy = -sum(p * np.log2(p) for p in probabilities if p > 0)

        bigrams = _ngrams(tokens, 2)
        unique_bigrams = set(bigrams)
        ngram_diversity = len(unique_bigrams) / len(bigrams) if len(bigrams) > 0 else 0.0

        overall_score = (
            unique_ratio * 0.3
            + ttr * 0.2
            + min(entropy / 10, 1) * 0.3
            + ngram_diversity * 0.2
        )

        return DiversityMetrics(
            unique_tokens_ratio=round(unique_ratio, 4),
            type_token_ratio=round(ttr, 4),
            entropy=round(entropy, 4),
            ngram_diversity=round(ngram_diversity, 4),
            overall_score=round(overall_score, 4),
        )
