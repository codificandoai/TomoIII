"""Vector store con backends simple, FAISS y pgvector para UC-266."""
from __future__ import annotations

import hashlib
import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


try:
    import faiss  # type: ignore
    _FAISS_AVAILABLE = True
except Exception:  # pragma: no cover
    _FAISS_AVAILABLE = False


try:
    import psycopg2  # type: ignore
    _PSYCOPG2_AVAILABLE = True
except Exception:  # pragma: no cover
    _PSYCOPG2_AVAILABLE = False


class VectorStoreBackend(ABC):
    """Interfaz común para los backends de vector store."""

    @abstractmethod
    def add(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        ...

    @abstractmethod
    def search(
        self, query: str, top_k: int = 5
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        ...

    @abstractmethod
    def clear(self) -> None:
        ...


class _Embedding:
    """Utilidad de embedding determinista por hash (para demostración)."""

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def __call__(self, text: str) -> np.ndarray:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)
        rng = np.random.default_rng(seed)
        vec = rng.random(self.dim).astype(np.float32)
        norm = np.linalg.norm(vec)
        return vec if norm == 0 else vec / norm


class SimpleVectorStoreBackend(VectorStoreBackend):
    """Backend en memoria/JSON basado en similitud del coseno."""

    def __init__(self, dim: int, path: Optional[str] = None) -> None:
        self.dim = dim
        self.path = path or ""
        self.embed = _Embedding(dim)
        self.ids: List[str] = []
        self.vectors: List[np.ndarray] = []
        self.metadatas: List[Dict[str, Any]] = []
        if self.path and os.path.exists(self.path):
            self._load()

    def add(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        record_id = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        vec = self.embed(text)
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
        q_vec = self.embed(query)
        matrix = np.array(self.vectors)
        similarities = (matrix @ q_vec).tolist()
        ranked = sorted(
            [(self.ids[i], similarities[i], self.metadatas[i]) for i in range(len(self.ids))],
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_k]

    def clear(self) -> None:
        self.ids = []
        self.vectors = []
        self.metadatas = []
        self._persist()

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


class FaissVectorStoreBackend(VectorStoreBackend):
    """Backend FAISS para búsqueda aproximada de vecinos más cercanos."""

    def __init__(self, dim: int, path: Optional[str] = None) -> None:
        if not _FAISS_AVAILABLE:
            raise RuntimeError("FAISS no está instalado. Usa backend='simple'.")
        self.dim = dim
        self.path = path or ""
        self.embed = _Embedding(dim)
        self.metadatas: Dict[str, Dict[str, Any]] = {}
        self.index = faiss.IndexFlatIP(dim)  # producto interno = coseno sobre vectores normalizados
        self._id_to_idx: Dict[str, int] = {}
        self._idx_to_id: Dict[int, str] = {}
        self._counter = 0
        if self.path and os.path.exists(self.path):
            self._load()

    def add(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        record_id = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        vec = self.embed(text).astype(np.float32).reshape(1, -1)
        if record_id in self._id_to_idx:
            # FAISS no soporta actualización in-place; se reemplaza por remove+add
            self._remove(record_id)
        idx = self._counter
        self._counter += 1
        self.index.add(vec)
        self._id_to_idx[record_id] = idx
        self._idx_to_id[idx] = record_id
        self.metadatas[record_id] = metadata or {}
        self._persist()
        return record_id

    def _remove(self, record_id: str) -> None:
        # Recrear índice sin el vector a eliminar (suficiente para datasets pequeños)
        idx = self._id_to_idx.pop(record_id, None)
        if idx is None:
            return
        self._idx_to_id.pop(idx, None)
        self.metadatas.pop(record_id, None)
        all_vectors = []
        ids = []
        for i in range(self._counter):
            if i == idx:
                continue
            rid = self._idx_to_id.get(i)
            if rid is None:
                continue
            all_vectors.append(self.embed(rid).astype(np.float32))
            ids.append(i)
        self.index = faiss.IndexFlatIP(self.dim)
        self._id_to_idx = {}
        self._idx_to_id = {}
        self._counter = 0
        if all_vectors:
            self.index.add(np.array(all_vectors))
            for new_i, old_i in enumerate(ids):
                self._id_to_idx[old_i] = new_i
                self._idx_to_id[new_i] = old_i

    def search(
        self, query: str, top_k: int = 5
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        if self.index.ntotal == 0:
            return []
        q_vec = self.embed(query).astype(np.float32).reshape(1, -1)
        distances, indices = self.index.search(q_vec, min(top_k, self.index.ntotal))
        results = []
        for score, idx in zip(distances[0], indices[0]):
            rid = self._idx_to_id.get(int(idx))
            if rid is None:
                continue
            results.append((rid, float(score), self.metadatas.get(rid, {})))
        return results

    def clear(self) -> None:
        self.index = faiss.IndexFlatIP(self.dim)
        self.metadatas = {}
        self._id_to_idx = {}
        self._idx_to_id = {}
        self._counter = 0

    def _persist(self) -> None:
        if not self.path:
            return
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            faiss.write_index(self.index, self.path)
            with open(self.path + ".meta", "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "metadatas": self.metadatas,
                        "id_to_idx": self._id_to_idx,
                        "idx_to_id": self._idx_to_id,
                        "counter": self._counter,
                    },
                    f,
                    ensure_ascii=False,
                )
        except OSError:
            pass

    def _load(self) -> None:
        try:
            self.index = faiss.read_index(self.path)
            meta_path = self.path + ".meta"
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.metadatas = data.get("metadatas", {})
                self._id_to_idx = {int(k): v for k, v in data.get("id_to_idx", {}).items()}
                self._idx_to_id = {int(k): v for k, v in data.get("idx_to_id", {}).items()}
                self._counter = data.get("counter", 0)
        except Exception:
            self.index = faiss.IndexFlatIP(self.dim)


class PgvectorVectorStoreBackend(VectorStoreBackend):
    """Backend pgvector para PostgreSQL (requiere psycopg2 y extensión pgvector)."""

    def __init__(self, dim: int, config: Optional[Dict[str, Any]] = None) -> None:
        if not _PSYCOPG2_AVAILABLE:
            raise RuntimeError("psycopg2 no está instalado. Usa backend='simple'.")
        self.dim = dim
        self.cfg = config or {}
        self.embed = _Embedding(dim)
        self.conn = psycopg2.connect(
            host=self.cfg.get("pg_host", "localhost"),
            port=self.cfg.get("pg_port", 5432),
            user=self.cfg.get("pg_user", ""),
            password=self.cfg.get("pg_password", ""),
            dbname=self.cfg.get("pg_db", ""),
        )
        self.table = self.cfg.get("pg_table", "uc266_vectors")
        self._init_table()

    def _init_table(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(f"CREATE TABLE IF NOT EXISTS {self.table} (id TEXT PRIMARY KEY, vector vector(%s), metadata JSONB)", (self.dim,))
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table}_vector ON {self.table} USING ivfflat (vector vector_cosine_ops)")
            self.conn.commit()

    def add(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        record_id = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        vec = self.embed(text).tolist()
        meta = json.dumps(metadata or {})
        with self.conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {self.table} (id, vector, metadata) VALUES (%s, %s, %s) ON CONFLICT (id) DO UPDATE SET vector=EXCLUDED.vector, metadata=EXCLUDED.metadata",
                (record_id, vec, meta),
            )
            self.conn.commit()
        return record_id

    def search(
        self, query: str, top_k: int = 5
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        vec = self.embed(query).tolist()
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT id, metadata, vector <=> %s::vector AS distance FROM {self.table} ORDER BY vector <=> %s::vector LIMIT %s",
                (vec, vec, top_k),
            )
            rows = cur.fetchall()
        return [(row[0], 1.0 - float(row[2]), json.loads(row[1] or "{}")) for row in rows]

    def clear(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(f"DELETE FROM {self.table}")
            self.conn.commit()


class VectorStore:
    """Fachada que selecciona el backend configurado."""

    def __init__(self, backend: str, dim: int, config: Optional[Dict[str, Any]] = None) -> None:
        self.backend = backend
        if backend == "faiss":
            self._store: VectorStoreBackend = FaissVectorStoreBackend(dim, config.get("path") if config else None)
        elif backend == "pgvector":
            self._store = PgvectorVectorStoreBackend(dim, config)
        else:
            self._store = SimpleVectorStoreBackend(dim, config.get("path") if config else None)

    def add(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        return self._store.add(text, metadata)

    def search(
        self, query: str, top_k: int = 5
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        return self._store.search(query, top_k)

    def clear(self) -> None:
        self._store.clear()


# Alias hacia atrás para compatibilidad con tests de UC-265
SimpleVectorStore = SimpleVectorStoreBackend
