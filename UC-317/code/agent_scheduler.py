"""UC-317 — Agent Scheduler: planificación simple de agentes concurrentes."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledAgent:
    agent_id: str
    task_id: str
    goal: str
    status: AgentStatus = AgentStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    trace: List[str] = field(default_factory=list)


class AgentScheduler:
    """Scheduler FIFO simple con soporte para status y resultados."""

    def __init__(self, max_concurrent: int = 4) -> None:
        self.max_concurrent = max_concurrent
        self._queue: List[ScheduledAgent] = []
        self._running: Dict[str, ScheduledAgent] = {}
        self._completed: List[ScheduledAgent] = []
        self._accepting_tasks: bool = True

    def schedule(self, agent_id: str, goal: str, task_id: Optional[str] = None) -> ScheduledAgent:
        if not self._accepting_tasks:
            raise RuntimeError("scheduler is not accepting new tasks (shutdown in progress)")
        task = ScheduledAgent(
            agent_id=agent_id,
            task_id=task_id or f"task_{uuid.uuid4().hex[:8]}",
            goal=goal,
        )
        self._queue.append(task)
        return task

    def tick(self, runner) -> List[ScheduledAgent]:
        """Ejecuta tareas pendientes hasta el límite de concurrencia."""
        started: List[ScheduledAgent] = []
        while self._queue and len(self._running) < self.max_concurrent:
            task = self._queue.pop(0)
            task.status = AgentStatus.RUNNING
            self._running[task.task_id] = task
            started.append(task)
            try:
                result = runner(task.agent_id, task.goal)
                task.result = result
                task.status = AgentStatus.COMPLETED
            except Exception as exc:
                task.result = {"error": str(exc)}
                task.status = AgentStatus.FAILED
            finally:
                self._completed.append(task)
                self._running.pop(task.task_id, None)
        return started

    def status(self) -> Dict[str, Any]:
        return {
            "pending": len(self._queue),
            "running": len(self._running),
            "completed": len(self._completed),
            "max_concurrent": self.max_concurrent,
        }

    def list_tasks(self) -> List[Dict[str, Any]]:
        all_tasks = self._queue + list(self._running.values()) + self._completed
        return [
            {
                "agent_id": t.agent_id,
                "task_id": t.task_id,
                "goal": t.goal,
                "status": t.status.value,
                "result": t.result,
            }
            for t in all_tasks
        ]

    # -------------------------------------------------------------------
    # UC-324 Safe Shutdown Adapter
    # -------------------------------------------------------------------

    def stop_accepting_tasks(self, shutdown_id: str = "") -> Dict[str, Any]:
        """UC-324 safe shutdown: stop accepting new tasks immediately."""
        self._accepting_tasks = False
        return {
            "adapter": "uc317_scheduler",
            "stopped": True,
            "shutdown_id": shutdown_id,
            "pending": len(self._queue),
            "running": len(self._running),
        }

    def drain_and_cancel(self, shutdown_id: str = "", timeout_seconds: float = 30.0) -> Dict[str, Any]:
        """UC-324 safe shutdown: drain/cancel pending and running tasks.

        Deterministic simulation: cancels pending immediately, marks running
        as cancelled. No threads required.
        """
        cancelled = 0
        drained = 0

        # Cancel pending tasks
        for task in self._queue:
            task.status = AgentStatus.CANCELLED
            task.result = {"cancelled_by": "safe_shutdown", "shutdown_id": shutdown_id}
            self._completed.append(task)
            cancelled += 1
        self._queue.clear()

        # Cancel running tasks
        for task_id, task in list(self._running.items()):
            task.status = AgentStatus.CANCELLED
            task.result = {"cancelled_by": "safe_shutdown", "shutdown_id": shutdown_id}
            self._completed.append(task)
            cancelled += 1
        drained = len(self._running)
        self._running.clear()

        return {
            "adapter": "uc317_scheduler",
            "drained": drained,
            "cancelled": cancelled,
            "shutdown_id": shutdown_id,
        }

    def resume_accepting_tasks(self) -> Dict[str, Any]:
        """UC-324 reactivation: resume accepting tasks."""
        self._accepting_tasks = True
        return {"adapter": "uc317_scheduler", "accepting": True}

    @property
    def is_accepting_tasks(self) -> bool:
        return self._accepting_tasks
