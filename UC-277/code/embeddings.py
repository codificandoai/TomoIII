"""SimpleEmbeddingModel — Embeddings hash-based para UC-277.

Modelo de embeddings determinista basado en hashing (bag-of-words + MD5).
En produccion: reemplazar con OpenAI embeddings, SentenceTransformers, etc.

Inspirado en aiming-lab/SimpleMem: Store -> Index (embeddings) -> Retrieve.
"""
from __future__ import annotations

import hashlib
import math
from typing import List


class SimpleEmbeddingModel:
    """Modelo de embeddings simplificado, determinista."""

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim
        self._cache: dict = {}

    def encode(self, text: str) -> List[float]:
        """Genera embedding normalizado para un texto."""
        if text in self._cache:
            return self._cache[text]

        embedding = [0.0] * self.dim
        words = text.lower().split()
        if not words:
            self._cache[text] = embedding
            return embedding

        for i, word in enumerate(words):
            word_hash = int(hashlib.md5(word.encode()).hexdigest(), 16)
            for j in range(self.dim):
                idx = (word_hash + j * 31 + i * 17) % self.dim
                embedding[idx] += math.cos(word_hash * (j + 1)) / math.sqrt(len(words))

        # Normaliza L2
        norm = math.sqrt(sum(x * x for x in embedding)) or 1.0
        embedding = [x / norm for x in embedding]

        self._cache[text] = embedding
        return embedding

    def similarity(self, a: List[float], b: List[float]) -> float:
        """Coseno de similitud entre dos embeddings."""
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
        norm_b = math.sqrt(sum(x * x for x in b)) or 1.0
        return dot / (norm_a * norm_b)
