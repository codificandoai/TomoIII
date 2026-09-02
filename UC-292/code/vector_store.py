"""Vector store simple para embeddings de estados/acciones de UC-265."""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class SimpleVectorStore:
    """Vector store ligero basado en numpy + similitud del coseno.

    Soporta persistencia opcional a disco como JSON. Puede reemplazarse por
    FAISS/Weaviate/pgvector en producción sin cambiar la interfaz.
    """

    def __init__(self, dim: int = 16, path: Optional[str] = None) -> None:
        self.dim = dim
        self.path = path or ""
        self.ids: List[str] = []
        self.vectors: List[np.ndarray] = []
        self.metadatas: List[Dict[str, Any]] = []
        if self.path and os.path.exists(self.path):
            self._load()

    def _embedding(self, text: str) -> np.ndarray:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)
        rng = np.random.default_rng(seed)
        vec = rng.random(self.dim).astype(np.float64)
        norm = np.linalg.norm(vec)
        return vec if norm == 0 else vec / norm

    def add(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        record_id = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        vec = self._embedding(text)
        if record_id in self.ids:
            idx = self.ids.index(record_id)
            self.vectors[idx] = vec
            self.metadatas[idx] = metadata or {}
        else:
            self.ids.append(record_id)
            self.vectors.append(vec)
            self.metadatas.append(metadata or {})
        self._persist()
        return record_id

    def search(
        self, query: str, top_k: int = 5
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        if not self.vectors:
            return []
        q_vec = self._embedding(query)
        matrix = np.array(self.vectors)
        similarities = (matrix @ q_vec).tolist()
        ranked = sorted(
            [(self.ids[i], similarities[i], self.metadatas[i]) for i in range(len(self.ids))],
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_k]

    def _persist(self) -> None:
        if not self.path:
            return
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            data = {
                "dim": self.dim,
                "ids": self.ids,
                "vectors": [v.tolist() for v in self.vectors],
                "metadatas": self.metadatas,
            }
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError:
            pass

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.dim = data.get("dim", self.dim)
            self.ids = data.get("ids", [])
            self.vectors = [np.array(v) for v in data.get("vectors", [])]
            self.metadatas = data.get("metadatas", [])
        except (json.JSONDecodeError, OSError):
            self.ids = []
            self.vectors = []
            self.metadatas = []
