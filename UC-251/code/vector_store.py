"""Almacén vectorial con FAISS opcional y fallback a fuerza bruta numpy."""
from __future__ import annotations

import logging
from typing import Callable, List, Optional

import numpy as np

from config import VectorStoreConfig
from models import Chunk

logger = logging.getLogger("uc251-vector-store")


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


class BaseVectorStore:
    """Interfaz del almacén vectorial."""

    def add_chunks(self, chunks: List[Chunk], embeddings: np.ndarray) -> None:
        ...

    def search(
        self,
        query_vec: np.ndarray,
        top_k: int = 10,
        filter_fn: Optional[Callable[[Chunk], bool]] = None,
    ) -> List[tuple[Chunk, float]]:
        ...

    def count(self) -> int:
        ...


class BruteForceVectorStore(BaseVectorStore):
    """Implementación CPU pura con similitud coseno."""

    def __init__(self, config: VectorStoreConfig):
        self.config = config
        self.chunks: List[Chunk] = []
        self.embeddings: Optional[np.ndarray] = None

    def add_chunks(self, chunks: List[Chunk], embeddings: np.ndarray) -> None:
        if len(chunks) != embeddings.shape[0]:
            raise ValueError("chunks y embeddings deben tener la misma longitud")
        if embeddings.shape[0] == 0:
            return
        vectors = _normalize(embeddings) if embeddings.dtype != np.float32 else embeddings
        if self.embeddings is None:
            self.embeddings = vectors
        else:
            self.embeddings = np.vstack([self.embeddings, vectors])
        self.chunks.extend(chunks)

    def search(
        self,
        query_vec: np.ndarray,
        top_k: int = 10,
        filter_fn: Optional[Callable[[Chunk], bool]] = None,
    ) -> List[tuple[Chunk, float]]:
        if self.embeddings is None or len(self.chunks) == 0:
            return []
        q = query_vec.reshape(1, -1).astype(np.float32)
        q = _normalize(q)
        scores = (self.embeddings @ q.T).flatten()
        indices = np.argsort(-scores)
        results: List[tuple[Chunk, float]] = []
        for idx in indices:
            chunk = self.chunks[int(idx)]
            if filter_fn and not filter_fn(chunk):
                continue
            results.append((chunk, float(scores[int(idx)])))
            if len(results) >= top_k:
                break
        return results

    def count(self) -> int:
        return len(self.chunks)


class FaissVectorStore(BaseVectorStore):
    """Implementación sobre FAISS (índice Flat IP + normalización L2)."""

    def __init__(self, config: VectorStoreConfig):
        self.config = config
        try:
            import faiss
        except Exception as exc:  # pragma: no cover
            raise ImportError("faiss-cpu no está instalado") from exc
        self.faiss = faiss
        self.chunks: List[Chunk] = []
        self.index: Optional[faiss.Index] = None
        self.dim: Optional[int] = None

    def add_chunks(self, chunks: List[Chunk], embeddings: np.ndarray) -> None:
        if len(chunks) != embeddings.shape[0]:
            raise ValueError("chunks y embeddings deben tener la misma longitud")
        if embeddings.shape[0] == 0:
            return
        vectors = _normalize(embeddings).astype("float32")
        if self.index is None:
            self.dim = vectors.shape[1]
            self.index = self.faiss.IndexFlatIP(self.dim)
        elif vectors.shape[1] != self.dim:
            raise ValueError("Dimensión de embeddings inconsistente")
        self.index.add(vectors)
        self.chunks.extend(chunks)

    def search(
        self,
        query_vec: np.ndarray,
        top_k: int = 10,
        filter_fn: Optional[Callable[[Chunk], bool]] = None,
    ) -> List[tuple[Chunk, float]]:
        if self.index is None or self.index.ntotal == 0:
            return []
        q = _normalize(query_vec.reshape(1, -1)).astype("float32")
        k_search = top_k * 3 if filter_fn else top_k
        scores, ids = self.index.search(q, min(k_search, self.index.ntotal))
        results: List[tuple[Chunk, float]] = []
        for score, idx in zip(scores[0], ids[0]):
            if idx == -1:
                continue
            chunk = self.chunks[int(idx)]
            if filter_fn and not filter_fn(chunk):
                continue
            results.append((chunk, float(score)))
            if len(results) >= top_k:
                break
        return results

    def count(self) -> int:
        return len(self.chunks)


def build_vector_store(config: VectorStoreConfig) -> BaseVectorStore:
    if config.backend in ("faiss", "auto"):
        try:
            return FaissVectorStore(config)
        except Exception as exc:  # pragma: no cover
            logger.warning("FAISS no disponible (%s); usando fuerza bruta", exc)
    return BruteForceVectorStore(config)
