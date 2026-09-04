"""Memoria a largo plazo (vectorial / semántica) para UC-296."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "UC-295", "code")))

import numpy as np

from memory_config import VectorMemoryConfig
from memory_types import MemoryResult, MemoryIntent


class LongTermMemory:
    """Almacén episódico/semántico basado en embeddings y similitud del coseno.

    En producción se reemplaza por pgvector/Pinecone/ChromaDB sin cambiar la
    interfaz. Si ``use_pgvector`` está activo y ``pg_uri`` es válida, intenta
    usar PostgreSQL+pgvector; de lo contrario cae en un almacén en memoria con
    persistencia JSON opcional.
    """

    def __init__(self, config: Optional[VectorMemoryConfig] = None) -> None:
        self.config = config or VectorMemoryConfig()
        self._pg_table = "uc296_long_term_memory"
        if self.config.use_pgvector and self.config.pg_uri:
            self._pg_conn = self._init_pgvector()
        else:
            self._pg_conn = None
        self._memory: List[Dict[str, Any]] = []
        self._vectors: List[np.ndarray] = []
        if self.config.vector_store_path and os.path.exists(self.config.vector_store_path):
            self._load()

    def _init_pgvector(self) -> Optional[Any]:
        try:
            import psycopg2
            conn = psycopg2.connect(self.config.pg_uri)
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self._pg_table} (
                        id TEXT PRIMARY KEY,
                        text TEXT NOT NULL,
                        embedding vector(%s),
                        metadata JSONB,
                        timestamp TIMESTAMPTZ DEFAULT NOW()
                    )
                """, (self.config.vector_dim,))
            conn.commit()
            return conn
        except Exception:
            return None

    def _embedding(self, text: str) -> np.ndarray:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)
        rng = np.random.default_rng(seed)
        vec = rng.random(self.config.vector_dim).astype(np.float64)
        norm = np.linalg.norm(vec)
        return vec if norm == 0 else vec / norm

    def add(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        record_id = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        vec = self._embedding(text)
        if self._pg_conn is not None:
            try:
                import psycopg2
                with self._pg_conn.cursor() as cur:
                    cur.execute(
                        f"""
                        INSERT INTO {self._pg_table} (id, text, embedding, metadata)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            text = EXCLUDED.text,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata
                        """,
                        (record_id, text, vec.tolist(), json.dumps(metadata or {}))
                    )
                self._pg_conn.commit()
            except Exception:
                pass
        self._memory.append({
            "id": record_id,
            "text": text,
            "embedding": vec,
            "metadata": metadata or {},
        })
        self._persist()
        return record_id

    def search(self, query: str, top_k: Optional[int] = None) -> List[Tuple[str, float, str, Dict[str, Any]]]:
        top_k = top_k or self.config.top_k
        q_vec = self._embedding(query)
        if self._pg_conn is not None:
            try:
                import psycopg2
                with self._pg_conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT id, text, metadata, 1 - (embedding <=> %s::vector) AS similarity
                        FROM {self._pg_table}
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (q_vec.tolist(), q_vec.tolist(), top_k),
                    )
                    rows = cur.fetchall()
                    return [
                        (row[0], float(row[3]), row[1], row[2] or {})
                        for row in rows
                        if float(row[3]) > self.config.similarity_threshold
                    ]
            except Exception:
                pass
        if not self._memory:
            return []
        similarities = []
        for doc in self._memory:
            sim = float(np.dot(q_vec, doc["embedding"]) / (
                np.linalg.norm(q_vec) * np.linalg.norm(doc["embedding"]) + 1e-9
            ))
            similarities.append((doc, sim))
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [
            (doc["id"], sim, doc["text"], doc["metadata"])
            for doc, sim in similarities[:top_k]
            if sim > self.config.similarity_threshold
        ]

    def retrieve(self, query: str) -> MemoryResult:
        start = __import__("time").time()
        results = self.search(query)
        latency = (__import__("time").time() - start) * 1000
        if results:
            return MemoryResult(
                intent=MemoryIntent.SEMANTIC_RECALL,
                source="LongTermMemory (Vectorial)",
                data=[{"id": r[0], "similarity": round(r[1], 4), "text": r[2]} for r in results],
                latency_ms=latency,
                confidence=round(results[0][1], 4),
            )
        return MemoryResult(
            intent=MemoryIntent.SEMANTIC_RECALL,
            source="LongTermMemory (Vectorial)",
            data="No se encontraron experiencias pasadas similares.",
            latency_ms=latency,
            confidence=0.0,
        )

    def _persist(self) -> None:
        if not self.config.vector_store_path:
            return
        try:
            os.makedirs(os.path.dirname(self.config.vector_store_path) or ".", exist_ok=True)
            import json as _json
            data = {
                "dim": self.config.vector_dim,
                "records": [
                    {
                        "id": r["id"],
                        "text": r["text"],
                        "embedding": r["embedding"].tolist(),
                        "metadata": r["metadata"],
                    }
                    for r in self._memory
                ],
            }
            with open(self.config.vector_store_path, "w", encoding="utf-8") as f:
                _json.dump(data, f, ensure_ascii=False)
        except OSError:
            pass

    def _load(self) -> None:
        try:
            import json as _json
            with open(self.config.vector_store_path, "r", encoding="utf-8") as f:
                data = _json.load(f)
            for r in data.get("records", []):
                self._memory.append({
                    "id": r["id"],
                    "text": r["text"],
                    "embedding": np.array(r["embedding"]),
                    "metadata": r.get("metadata", {}),
                })
        except Exception:
            pass
