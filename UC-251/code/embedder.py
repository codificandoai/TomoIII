"""Encoders de embeddings densos con fallback determinista (stub)."""
from __future__ import annotations

import hashlib
import logging
import math
from abc import ABC, abstractmethod
from typing import List

import numpy as np

from config import EmbedderConfig

logger = logging.getLogger("uc251-embedder")


class BaseEmbedder(ABC):
    """Interfaz base para encoders."""

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Devuelve una lista de vectores normalizados (o no) según config."""
        ...

    def embed_text(self, text: str) -> List[float]:
        return self.embed_texts([text])[0]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_text(text)


class StubEmbedder(BaseEmbedder):
    """Encoder determinista sin dependencias ni descargas de red.

    Útil en tests, CI y entornos aislados. En producción debe reemplazarse
    por un modelo de sentence-transformers (BGE, E5, GTE, etc.).
    """

    def __init__(self, config: EmbedderConfig):
        self.config = config
        self.dim = config.embedding_dim

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        vectors = [self._hash_vector(t) for t in texts]
        if self.config.normalize:
            vectors = [self._normalize(v) for v in vectors]
        return vectors

    def _hash_vector(self, text: str) -> List[float]:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        rng = self._make_rng(seed)
        return [rng() for _ in range(self.dim)]

    @staticmethod
    def _make_rng(seed: int):
        # Generador congruencial lineal simple y determinista
        state = seed % (2**32)

        def next_val():
            nonlocal state
            state = (1103515245 * state + 12345) & 0x7FFFFFFF
            return float(state) / 0x7FFFFFFF - 0.5

        return next_val

    @staticmethod
    def _normalize(vec: List[float]) -> List[float]:
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0:
            return vec
        return [x / norm for x in vec]


class SentenceTransformerEmbedder(BaseEmbedder):
    """Envoltorio sobre sentence-transformers."""

    def __init__(self, config: EmbedderConfig):
        self.config = config
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:  # pragma: no cover
            raise ImportError(
                "sentence-transformers no está instalado. "
                "Use StubEmbedder o instale la dependencia."
            ) from exc
        logger.info("Cargando modelo de embeddings: %s", config.model_name)
        self.model = SentenceTransformer(config.model_name)
        self.dim = self.model.get_sentence_embedding_dimension() or config.embedding_dim

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        import numpy as np

        vectors = self.model.encode(
            texts,
            batch_size=self.config.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=self.config.normalize,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]


def build_embedder(config: EmbedderConfig) -> BaseEmbedder:
    if config.model_name == "stub":
        return StubEmbedder(config)
    return SentenceTransformerEmbedder(config)
