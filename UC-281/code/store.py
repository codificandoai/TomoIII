"""SQLite audit store for synchronized pipeline runs."""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import List

from models import PipelineRun


class RunStore:
    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.RLock()
        with self._conn:
            self._conn.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, audit_hash TEXT NOT NULL, payload TEXT NOT NULL)")

    def save(self, run: PipelineRun) -> None:
        with self._lock, self._conn:
            self._conn.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?)",
                               (run.run_id, run.audit_hash(), json.dumps(run.public_dict(), default=str)))

    def get(self, run_id: str) -> dict:
        with self._lock:
            row = self._conn.execute("SELECT audit_hash,payload FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if not row:
            raise KeyError(f"run not found: {run_id}")
        return {"audit_hash": row[0], "run": json.loads(row[1])}

    def list(self, limit: int = 50) -> List[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT run_id,audit_hash,payload FROM runs ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        return [{"run_id": row[0], "audit_hash": row[1], "run": json.loads(row[2])} for row in rows]