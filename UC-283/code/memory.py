"""Persistent Reflexion-style lesson memory backed by SQLite."""
from __future__ import annotations

import sqlite3
import threading
from collections import Counter
from typing import List


class LessonMemory:
    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.RLock()
        with self._conn:
            self._conn.execute("CREATE TABLE IF NOT EXISTS lessons (id INTEGER PRIMARY KEY, product_id TEXT, category TEXT, lesson TEXT, old_price REAL, new_price REAL)")

    def learn(self, product_id: str, category: str, lesson: str,
              old_price: float, new_price: float) -> None:
        with self._lock, self._conn:
            self._conn.execute("INSERT INTO lessons(product_id,category,lesson,old_price,new_price) VALUES (?,?,?,?,?)",
                               (product_id, category, lesson, old_price, new_price))

    def recall(self, product_id: str, limit: int = 5) -> List[str]:
        with self._lock:
            rows = self._conn.execute("SELECT lesson FROM lessons WHERE product_id=? ORDER BY id DESC LIMIT ?",
                                      (product_id, limit)).fetchall()
        return [row[0] for row in rows]

    def stats(self, product_id: str) -> dict:
        with self._lock:
            rows = self._conn.execute("SELECT category FROM lessons WHERE product_id=?", (product_id,)).fetchall()
        counts = Counter(row[0] for row in rows)
        return {"total": sum(counts.values()), "by_category": dict(counts)}