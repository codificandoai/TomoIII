"""Typed domain models for hierarchical goal decomposition."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum, IntEnum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class TaskPriority(IntEnum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    OPTIONAL = 5


class PlannerType(str, Enum):
    LANGGRAPH = "langgraph"
    TDAG = "tdag"
    REACTREE = "reactree"


@dataclass
class Task:
    title: str
    description: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    parent_id: Optional[str] = None
    depth: int = 0
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    assigned_agent: Optional[str] = None
    max_retries: int = 1
    attempts: int = 0
    timeout_seconds: float = 30.0
    output: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def public_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["priority"] = self.priority.name.lower()
        data["status"] = self.status.value
        return data


@dataclass
class Goal:
    description: str
    context: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex[:16])
    planner: PlannerType = PlannerType.LANGGRAPH
    status: TaskStatus = TaskStatus.PENDING
    tasks: Dict[str, Task] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    version: int = 1

    @property
    def progress(self) -> float:
        if not self.tasks:
            return 0.0
        completed = sum(t.status in {TaskStatus.COMPLETED, TaskStatus.SKIPPED} for t in self.tasks.values())
        return completed / len(self.tasks)

    def public_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "description": self.description, "context": self.context,
            "planner": self.planner.value, "status": self.status.value,
            "progress": round(self.progress, 4), "version": self.version,
            "created_at": self.created_at, "completed_at": self.completed_at,
            "tasks": [t.public_dict() for t in self.tasks.values()],
        }


@dataclass(frozen=True)
class AgentSpec:
    id: str
    capabilities: List[str]
    max_concurrency: int = 2


@dataclass
class ExecutionEvent:
    goal_id: str
    event_type: str
    task_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: uuid4().hex[:12])


@dataclass
class ExecutionSummary:
    goal_id: str
    status: TaskStatus
    completed: int
    failed: int
    blocked: int
    skipped: int
    duration_seconds: float
    waves: int
    events: List[ExecutionEvent]

    def public_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    def audit_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.public_dict(), sort_keys=True, default=str).encode()).hexdigest()