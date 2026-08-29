"""EpisodicMemoryStore — Almacen de memoria episodica para UC-277.

Persistencia SQLite con busqueda:
- Semantica (embeddings + coseno + boost por importancia/recencia).
- Temporal (rango de fechas).
- Por tags.
- Por sesion.

Inspirado en:
- mem0ai/mem0: retiene memoria de usuario/sesion/agente persistente.
- jojopdq/HiMem: memoria jerarquica a largo plazo multi-turno.
"""
from __future__ import annotations

import json
import math
import sqlite3
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from embeddings import SimpleEmbeddingModel
from models import EpisodicMemory, IMPORTANCE_WEIGHTS, MemoryImportance


class EpisodicMemoryStore:
    """Almacen de memoria episodica con busqueda semantica y persistencia SQLite."""

    def __init__(self, embedding_model: SimpleEmbeddingModel,
                 db_path: str = ":memory:") -> None:
        self.embedding_model = embedding_model
        self.db_path = db_path
        self.episodes: Dict[str, EpisodicMemory] = {}
        self._conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self) -> None:
        c = self._conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS episodic_memory (
                episode_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                session_id TEXT,
                episode_type TEXT NOT NULL,
                timestamp REAL NOT NULL,
                summary TEXT NOT NULL,
                details_json TEXT,
                tags_json TEXT,
                importance TEXT,
                outcome_sentiment REAL,
                metrics_json TEXT,
                embedding_json TEXT,
                access_count INTEGER DEFAULT 0,
                last_accessed REAL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_agent_time ON episodic_memory(agent_id, timestamp)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_session ON episodic_memory(session_id)")
        self._conn.commit()

    def store(self, episode: EpisodicMemory) -> str:
        """Almacena episodio con embedding."""
        embedding = self.embedding_model.encode(episode.summary)
        episode = episode.model_copy(update={"embedding": embedding})
        self.episodes[episode.episode_id] = episode
        self._persist(episode)
        return episode.episode_id

    def recall_semantic(self, query: str, agent_id: str,
                        top_k: int = 5, min_similarity: float = 0.3) -> List[EpisodicMemory]:
        """Recupera episodios por similitud semantica con boost."""
        query_emb = self.embedding_model.encode(query)
        candidates = []

        for ep in self.episodes.values():
            if ep.agent_id != agent_id or ep.embedding is None:
                continue
            sim = self.embedding_model.similarity(query_emb, ep.embedding)
            if sim >= min_similarity:
                age_days = (time.time() - ep.timestamp) / 86400
                recency_boost = math.exp(-0.01 * age_days)
                importance_boost = IMPORTANCE_WEIGHTS.get(ep.importance, 0.6)
                score = sim * recency_boost * (0.5 + importance_boost)
                candidates.append((score, ep))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in candidates[:top_k]]

    def recall_by_time(self, agent_id: str, start_time: float, end_time: float,
                       episode_type: Optional[str] = None,
                       limit: int = 100) -> List[EpisodicMemory]:
        """Recupera episodios por rango temporal."""
        results = []
        for ep in self.episodes.values():
            if ep.agent_id != agent_id:
                continue
            if not (start_time <= ep.timestamp <= end_time):
                continue
            if episode_type and ep.episode_type != episode_type:
                continue
            results.append(ep)
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[:limit]

    def recall_by_session(self, session_id: str, limit: int = 100) -> List[EpisodicMemory]:
        """Recupera episodios de una sesion especifica."""
        results = [ep for ep in self.episodes.values() if ep.session_id == session_id]
        results.sort(key=lambda e: e.timestamp)
        return results[:limit]

    def recall_by_tag(self, agent_id: str, tag: str, limit: int = 50) -> List[EpisodicMemory]:
        """Recupera episodios por tag."""
        results = [
            ep for ep in self.episodes.values()
            if ep.agent_id == agent_id and tag in ep.tags
        ]
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[:limit]

    def get_stats(self, agent_id: str) -> Dict[str, Any]:
        """Estadisticas de vida del agente."""
        episodes = [ep for ep in self.episodes.values() if ep.agent_id == agent_id]
        if not episodes:
            return {"total_episodes": 0}

        by_type: Dict[str, int] = defaultdict(int)
        sentiments = []
        for ep in episodes:
            by_type[ep.episode_type] += 1
            sentiments.append(ep.outcome_sentiment)

        return {
            "total_episodes": len(episodes),
            "by_type": dict(by_type),
            "avg_sentiment": round(sum(sentiments) / len(sentiments), 4),
            "lifetime_days": round(
                (max(ep.timestamp for ep in episodes) - min(ep.timestamp for ep in episodes)) / 86400, 2
            ),
            "critical_count": sum(1 for ep in episodes if ep.importance == MemoryImportance.CRITICAL),
        }

    def _persist(self, ep: EpisodicMemory) -> None:
        c = self._conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO episodic_memory VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            ep.episode_id, ep.agent_id, ep.session_id, ep.episode_type,
            ep.timestamp, ep.summary, json.dumps(ep.details),
            json.dumps(ep.tags), ep.importance.value, ep.outcome_sentiment,
            json.dumps(ep.metrics), json.dumps(ep.embedding),
            ep.access_count, ep.last_accessed,
        ))
        self._conn.commit()
