"""SQLite checkpoint store for goals and execution events."""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import List, Optional

from models import ExecutionEvent, Goal, PlannerType, Task, TaskPriority, TaskStatus


class GoalStore:
    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.RLock()
        with self._conn:
            self._conn.execute("CREATE TABLE IF NOT EXISTS goals (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            self._conn.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, payload TEXT NOT NULL)")

    def save(self, goal: Goal, event: ExecutionEvent | None = None) -> None:
        with self._lock, self._conn:
            self._conn.execute("INSERT OR REPLACE INTO goals VALUES (?,?)",
                               (goal.id, json.dumps(goal.public_dict(), default=str)))
            if event:
                self._conn.execute("INSERT OR REPLACE INTO events VALUES (?,?,?)",
                                   (event.id, goal.id, json.dumps(event.__dict__, default=str)))

    def get(self, goal_id: str) -> Goal:
        with self._lock:
            row = self._conn.execute("SELECT payload FROM goals WHERE id=?", (goal_id,)).fetchone()
        if not row:
            raise KeyError(f"goal not found: {goal_id}")
        data = json.loads(row[0])
        goal = Goal(data["description"], data.get("context", {}), id=data["id"],
                    planner=PlannerType(data["planner"]), status=TaskStatus(data["status"]),
                    created_at=data["created_at"], completed_at=data.get("completed_at"), version=data["version"])
        for item in data["tasks"]:
            task = Task(item["title"], item.get("description", ""), id=item["id"],
                        parent_id=item.get("parent_id"), depth=item.get("depth", 0),
                        priority=TaskPriority[item["priority"].upper()], status=TaskStatus(item["status"]),
                        dependencies=item.get("dependencies", []), required_capabilities=item.get("required_capabilities", []),
                        assigned_agent=item.get("assigned_agent"), max_retries=item.get("max_retries", 1),
                        attempts=item.get("attempts", 0), timeout_seconds=item.get("timeout_seconds", 30),
                        output=item.get("output"), error=item.get("error"), started_at=item.get("started_at"),
                        completed_at=item.get("completed_at"), metadata=item.get("metadata", {}))
            goal.tasks[task.id] = task
        return goal

    def list(self) -> List[Goal]:
        with self._lock:
            ids = [row[0] for row in self._conn.execute("SELECT id FROM goals ORDER BY id")]
        return [self.get(goal_id) for goal_id in ids]

    def events(self, goal_id: str) -> List[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT payload FROM events WHERE goal_id=? ORDER BY rowid", (goal_id,)).fetchall()
        return [json.loads(row[0]) for row in rows]