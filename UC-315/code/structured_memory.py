"""Memoria estructurada (SQL + pgvector opcional) para UC-296."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional

from memory_config import StructuredMemoryConfig


class StructuredMemory:
    """Almacén estructurado de hechos: productos, usuarios, métricas."""

    _lock = threading.Lock()

    def __init__(self, config: Optional[StructuredMemoryConfig] = None) -> None:
        self.config = config or StructuredMemoryConfig()
        self._conn: Optional[Any] = None
        self._init_db()

    def _init_db(self) -> None:
        if self.config.sqlite_path:
            os.makedirs(os.path.dirname(self.config.sqlite_path) or ".", exist_ok=True)
            with sqlite3.connect(self.config.sqlite_path) as conn:
                self._create_tables(conn)
            return
        if self.config.pg_uri:
            try:
                import psycopg2
                self._conn = psycopg2.connect(self.config.pg_uri)
                self._create_tables(self._conn)
            except Exception:
                pass

    def _create_tables(self, conn: Any) -> None:
        ddl = [
            """
            CREATE TABLE IF NOT EXISTS facts (
                id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                attribute TEXT NOT NULL,
                value TEXT,
                metadata TEXT,
                timestamp TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS self_model (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                data TEXT NOT NULL,
                timestamp TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS performance_history (
                episode_id TEXT PRIMARY KEY,
                task TEXT,
                success INTEGER,
                metrics TEXT,
                context TEXT,
                policy_adjustments TEXT,
                timestamp TEXT
            )
            """,
        ]
        for stmt in ddl:
            conn.execute(stmt)
        conn.commit()

    def query(
        self,
        entity_type: str,
        entity_id: str,
        attribute: str,
    ) -> Optional[Any]:
        if self.config.sqlite_path:
            with sqlite3.connect(self.config.sqlite_path) as conn:
                row = conn.execute(
                    "SELECT value FROM facts WHERE entity_type = ? AND entity_id = ? AND attribute = ?",
                    (entity_type, entity_id, attribute),
                ).fetchone()
                if row:
                    return self._decode(row[0])
        return None

    def store(
        self,
        entity_type: str,
        entity_id: str,
        attribute: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        if not self.config.sqlite_path:
            return
        from datetime import datetime, timezone
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        key = f"{entity_type}:{entity_id}:{attribute}"
        with self._lock, sqlite3.connect(self.config.sqlite_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO facts (id, entity_type, entity_id, attribute, value, metadata, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    entity_type,
                    entity_id,
                    attribute,
                    self._encode(value),
                    json.dumps(metadata or {}),
                    ts,
                ),
            )
            conn.commit()

    def get_self_model(self) -> Optional[Dict[str, Any]]:
        if not self.config.sqlite_path:
            return None
        with sqlite3.connect(self.config.sqlite_path) as conn:
            row = conn.execute(
                "SELECT data FROM self_model WHERE id = 1"
            ).fetchone()
            if row:
                return json.loads(row[0])
        return None

    def save_self_model(self, data: Dict[str, Any]) -> None:
        if not self.config.sqlite_path:
            return
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        with self._lock, sqlite3.connect(self.config.sqlite_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO self_model (id, data, timestamp) VALUES (1, ?, ?)",
                (json.dumps(data), ts),
            )
            conn.commit()

    def save_performance(self, episode: Dict[str, Any]) -> None:
        if not self.config.sqlite_path:
            return
        from datetime import datetime, timezone
        ts = episode.get("timestamp") or datetime.now(timezone.utc).isoformat()
        with self._lock, sqlite3.connect(self.config.sqlite_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO performance_history
                (episode_id, task, success, metrics, context, policy_adjustments, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode.get("episode_id"),
                    episode.get("task"),
                    1 if episode.get("success") else 0,
                    json.dumps(episode.get("metrics", {})),
                    json.dumps(episode.get("context", {})),
                    json.dumps(episode.get("policy_adjustments", [])),
                    ts,
                ),
            )
            conn.commit()

    def get_performance_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.config.sqlite_path:
            return []
        with sqlite3.connect(self.config.sqlite_path) as conn:
            rows = conn.execute(
                "SELECT * FROM performance_history ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_perf(r) for r in rows]

    @staticmethod
    def _decode(value: str) -> Any:
        try:
            return json.loads(value)
        except Exception:
            return value

    @staticmethod
    def _encode(value: Any) -> str:
        return json.dumps(value)

    @staticmethod
    def _row_to_perf(row: tuple) -> Dict[str, Any]:
        return {
            "episode_id": row[0],
            "task": row[1],
            "success": bool(row[2]),
            "metrics": json.loads(row[3]) if row[3] else {},
            "context": json.loads(row[4]) if row[4] else {},
            "policy_adjustments": json.loads(row[5]) if row[5] else [],
            "timestamp": row[6],
        }
