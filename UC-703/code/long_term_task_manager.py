"""
UC-703 — Long Term Task Manager.

Gestiona tareas duraderas del runtime AGI: checkpoints, pausa, reanudación,
cancelación y timeout. Es la capa de durabilidad portátil antes de delegar a
Temporal.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Checkpoint:
    checkpoint_id: str = field(default_factory=lambda: f"chk-{uuid.uuid4().hex[:8]}")
    task_id: str = ""
    step_id: str = ""
    state: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "state": self.state,
            "created_at": self.created_at,
        }


@dataclass
class LongRunningTask:
    task_id: str = field(default_factory=lambda: f"lrt-{uuid.uuid4().hex[:8]}")
    objective_id: str = ""
    status: str = "pending"  # pending, running, paused, completed, failed, cancelled
    current_step_id: Optional[str] = None
    checkpoints: List[Checkpoint] = field(default_factory=list)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    timeout_seconds: float = 86400.0
    last_heartbeat: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "objective_id": self.objective_id,
            "status": self.status,
            "current_step_id": self.current_step_id,
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "timeout_seconds": self.timeout_seconds,
            "last_heartbeat": self.last_heartbeat,
        }


class LongTermTaskManager:
    """
    Mantiene el estado durable de tareas del runtime AGI.

    - Guarda checkpoints para recuperación ante fallos.
    - Permite pausar/reanudar/cancelar.
    - Detecta timeouts por inactividad.
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, LongRunningTask] = {}

    def create_task(self, objective_id: str, timeout_seconds: float = 86400.0) -> LongRunningTask:
        task = LongRunningTask(objective_id=objective_id, timeout_seconds=timeout_seconds)
        self._tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[LongRunningTask]:
        return self._tasks.get(task_id)

    def save_checkpoint(self, task_id: str, step_id: str, state: Dict[str, Any]) -> Optional[Checkpoint]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        checkpoint = Checkpoint(task_id=task_id, step_id=step_id, state=state)
        task.checkpoints.append(checkpoint)
        task.current_step_id = step_id
        task.last_heartbeat = time.time()
        return checkpoint

    def start_task(self, task_id: str) -> Optional[LongRunningTask]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        task.status = "running"
        task.started_at = time.time()
        task.last_heartbeat = time.time()
        return task

    def pause_task(self, task_id: str) -> Optional[LongRunningTask]:
        task = self._tasks.get(task_id)
        if not task or task.status not in ("pending", "running"):
            return None
        task.status = "paused"
        task.last_heartbeat = time.time()
        return task

    def resume_task(self, task_id: str) -> Optional[LongRunningTask]:
        task = self._tasks.get(task_id)
        if not task or task.status != "paused":
            return None
        task.status = "running"
        task.last_heartbeat = time.time()
        return task

    def cancel_task(self, task_id: str) -> Optional[LongRunningTask]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        task.status = "cancelled"
        task.finished_at = time.time()
        task.last_heartbeat = time.time()
        return task

    def complete_task(self, task_id: str) -> Optional[LongRunningTask]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        task.status = "completed"
        task.finished_at = time.time()
        task.last_heartbeat = time.time()
        return task

    def fail_task(self, task_id: str, error: str) -> Optional[LongRunningTask]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        task.status = "failed"
        task.finished_at = time.time()
        task.last_heartbeat = time.time()
        return task

    def recover_from_last_checkpoint(self, task_id: str) -> Optional[Checkpoint]:
        task = self._tasks.get(task_id)
        if not task or not task.checkpoints:
            return None
        return task.checkpoints[-1]

    def is_timed_out(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.status in ("completed", "failed", "cancelled"):
            return False
        return (time.time() - task.last_heartbeat) > task.timeout_seconds

    def list_tasks(self, status: Optional[str] = None) -> List[LongRunningTask]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks
