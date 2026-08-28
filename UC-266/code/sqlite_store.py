"""Persistencia de transiciones y observaciones en SQLite para UC-266."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional


class SQLiteStore:
    """Almacena transiciones, observaciones y lotes de entrenamiento en SQLite."""

    _lock = threading.Lock()

    def __init__(self, path: Optional[str] = None) -> None:
        self._path = path or ""
        self._initialized = False
        if self._path:
            self._init_db()

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transitions (
                    id TEXT PRIMARY KEY,
                    request_id TEXT,
                    prev_state TEXT,
                    action TEXT,
                    next_state TEXT,
                    reward REAL,
                    probability REAL,
                    info TEXT,
                    timestamp TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    id TEXT PRIMARY KEY,
                    action_type TEXT,
                    item_id TEXT,
                    predicted_success_prob REAL,
                    actual_success INTEGER,
                    actual_cost REAL,
                    reward REAL,
                    timestamp TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS training_batches (
                    id TEXT PRIMARY KEY,
                    data TEXT,
                    timestamp TEXT
                )
                """
            )
            conn.commit()
        self._initialized = True

    def save_transition(self, transition: Dict[str, Any]) -> None:
        if not self._path:
            return
        if not self._initialized:
            self._init_db()
        with self._lock, sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO transitions
                (id, request_id, prev_state, action, next_state, reward, probability, info, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transition.get("transition_id", ""),
                    transition.get("prev_state", {}).get("request_id", ""),
                    json.dumps(transition.get("prev_state", {})),
                    json.dumps(transition.get("action", {})),
                    json.dumps(transition.get("next_state", {})),
                    transition.get("reward", 0.0),
                    transition.get("probability", 1.0),
                    json.dumps(transition.get("info", {})),
                    transition.get("timestamp", ""),
                ),
            )
            conn.commit()

    def save_observation(self, observation: Dict[str, Any]) -> None:
        if not self._path:
            return
        if not self._initialized:
            self._init_db()
        with self._lock, sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO observations
                (id, action_type, item_id, predicted_success_prob, actual_success, actual_cost, reward, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation.get("observation_id", ""),
                    observation.get("action_type", ""),
                    observation.get("item_id", ""),
                    observation.get("predicted_success_prob", 1.0),
                    1 if observation.get("actual_success") else 0,
                    observation.get("actual_cost", 0.0),
                    observation.get("reward", 0.0),
                    observation.get("timestamp", ""),
                ),
            )
            conn.commit()

    def get_transitions(
        self, request_id: Optional[str] = None, limit: int = 10000
    ) -> List[Dict[str, Any]]:
        if not self._path or not self._initialized:
            return []
        with sqlite3.connect(self._path) as conn:
            if request_id:
                rows = conn.execute(
                    "SELECT * FROM transitions WHERE request_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (request_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM transitions ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [self._row_to_dict(row, "transitions") for row in rows]

    def get_observations(self, limit: int = 10000) -> List[Dict[str, Any]]:
        if not self._path or not self._initialized:
            return []
        with sqlite3.connect(self._path) as conn:
            rows = conn.execute(
                "SELECT * FROM observations ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row, "observations") for row in rows]

    def save_training_batch(self, batch: Dict[str, Any]) -> None:
        if not self._path:
            return
        if not self._initialized:
            self._init_db()
        with self._lock, sqlite3.connect(self._path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO training_batches (id, data, timestamp) VALUES (?, ?, ?)",
                (
                    batch.get("batch_id", ""),
                    json.dumps(batch),
                    batch.get("timestamp", ""),
                ),
            )
            conn.commit()

    def _row_to_dict(self, row: tuple, table: str) -> Dict[str, Any]:
        if table == "transitions":
            return {
                "transition_id": row[0],
                "request_id": row[1],
                "prev_state": json.loads(row[2]) if row[2] else {},
                "action": json.loads(row[3]) if row[3] else {},
                "next_state": json.loads(row[4]) if row[4] else {},
                "reward": row[5],
                "probability": row[6],
                "info": json.loads(row[7]) if row[7] else {},
                "timestamp": row[8],
            }
        if table == "observations":
            return {
                "observation_id": row[0],
                "action_type": row[1],
                "item_id": row[2],
                "predicted_success_prob": row[3],
                "actual_success": bool(row[4]),
                "actual_cost": row[5],
                "reward": row[6],
                "timestamp": row[7],
            }
        return {}
