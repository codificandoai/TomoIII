"""Parallel multi-agent DAG executor with retries, checkpoints and failure propagation."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any, Callable, Dict, List

from models import AgentSpec, ExecutionEvent, ExecutionSummary, Goal, Task, TaskStatus
from planners import topological_waves

TaskHandler = Callable[[Task, dict], Any]


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: Dict[str, tuple[AgentSpec, TaskHandler]] = {}

    def register(self, spec: AgentSpec, handler: TaskHandler) -> None:
        if spec.id in self._agents:
            raise ValueError(f"agent already registered: {spec.id}")
        self._agents[spec.id] = (spec, handler)

    def select(self, task: Task) -> tuple[AgentSpec, TaskHandler]:
        candidates = [entry for entry in self._agents.values()
                      if set(task.required_capabilities).issubset(set(entry[0].capabilities))]
        if not candidates:
            candidates = list(self._agents.values())
        if not candidates:
            raise ValueError("no agents registered")
        return sorted(candidates, key=lambda entry: entry[0].id)[0]


class DAGExecutor:
    def __init__(self, agents: AgentRegistry, max_workers: int = 8,
                 checkpoint: Callable[[Goal, ExecutionEvent], None] | None = None) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be positive")
        self.agents, self.max_workers, self.checkpoint = agents, max_workers, checkpoint

    def execute(self, goal: Goal) -> ExecutionSummary:
        started, events, wave_count = time.monotonic(), [], 0
        goal.status = TaskStatus.RUNNING
        self._event(goal, events, "goal_started")
        for wave in topological_waves(goal):
            runnable = []
            for task in wave:
                if task.status == TaskStatus.COMPLETED:
                    continue
                failed_dependencies = [goal.tasks[d] for d in task.dependencies
                                       if goal.tasks[d].status != TaskStatus.COMPLETED]
                if failed_dependencies:
                    task.status = TaskStatus.BLOCKED
                    task.error = "dependency did not complete"
                    self._event(goal, events, "task_blocked", task)
                else:
                    runnable.append(task)
            if not runnable:
                continue
            wave_count += 1
            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(runnable))) as pool:
                futures = {pool.submit(self._run_task, goal, task, events): task for task in runnable}
                for future, task in futures.items():
                    try:
                        future.result(timeout=task.timeout_seconds * (task.max_retries + 1) + 1)
                    except FutureTimeout:
                        task.status, task.error = TaskStatus.FAILED, "task timeout"
                        self._event(goal, events, "task_failed", task, {"error": task.error})
        counts = {status: sum(t.status == status for t in goal.tasks.values()) for status in TaskStatus}
        goal.status = TaskStatus.COMPLETED if counts[TaskStatus.COMPLETED] == len(goal.tasks) else TaskStatus.FAILED
        goal.completed_at, goal.version = time.time(), goal.version + 1
        self._event(goal, events, "goal_completed", payload={"status": goal.status.value})
        return ExecutionSummary(goal.id, goal.status, counts[TaskStatus.COMPLETED], counts[TaskStatus.FAILED],
                                counts[TaskStatus.BLOCKED], counts[TaskStatus.SKIPPED],
                                round(time.monotonic() - started, 6), wave_count, events)

    def _run_task(self, goal: Goal, task: Task, events: List[ExecutionEvent]) -> None:
        spec, handler = self.agents.select(task)
        task.assigned_agent, task.status, task.started_at = spec.id, TaskStatus.RUNNING, time.time()
        self._event(goal, events, "task_started", task, {"agent": spec.id})
        while task.attempts <= task.max_retries:
            task.attempts += 1
            try:
                task.output = handler(task, goal.context)
                task.status, task.completed_at, task.error = TaskStatus.COMPLETED, time.time(), None
                self._event(goal, events, "task_completed", task, {"attempt": task.attempts})
                return
            except Exception as exc:
                task.error = str(exc)
                self._event(goal, events, "task_retry", task, {"attempt": task.attempts, "error": task.error})
        task.status, task.completed_at = TaskStatus.FAILED, time.time()
        self._event(goal, events, "task_failed", task, {"error": task.error})

    def _event(self, goal: Goal, events: List[ExecutionEvent], event_type: str,
               task: Task | None = None, payload: dict | None = None) -> None:
        event = ExecutionEvent(goal.id, event_type, task.id if task else None, payload or {})
        events.append(event)
        if self.checkpoint:
            self.checkpoint(goal, event)


def build_default_registry() -> AgentRegistry:
    registry = AgentRegistry()
    capabilities = ["planning", "research", "architecture", "execution", "quality",
                    "communication", "risk", "synthesis", "reasoning"]
    for capability in capabilities:
        registry.register(AgentSpec(f"{capability}_agent", [capability]),
                          lambda task, context, cap=capability: {
                              "agent_capability": cap, "task": task.title,
                              "result": f"Completed {task.title}", "context_keys": sorted(context),
                          })
    return registry