"""
UC-703 — Modelos de datos para AGI Agent Runtime & Orchestrator.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionBackend(str, Enum):
    TEMPORAL = "temporal"
    STACKSTORM = "stackstorm"
    N8N = "n8n"
    LOCAL = "local"


class Capability(str, Enum):
    THINK = "think"              # UC-315/325
    REMEMBER = "remember"        # UC-326/296
    APPROVE = "approve"          # UC-290/300
    EXECUTE_LOCAL = "execute_local"  # UC-317
    EXECUTE_TEMPORAL = "execute_temporal"
    EXECUTE_STACKSTORM = "execute_stackstorm"
    EXECUTE_N8N = "execute_n8n"


@dataclass
class Objective:
    objective_id: str = field(default_factory=lambda: f"obj-{uuid.uuid4().hex[:8]}")
    description: str = ""
    agent_id: str = ""
    tenant_id: str = ""
    requested_by: str = ""
    capabilities_needed: List[Capability] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective_id": self.objective_id,
            "description": self.description,
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "requested_by": self.requested_by,
            "capabilities_needed": [c.value for c in self.capabilities_needed],
            "context": self.context,
            "created_at": self.created_at,
        }


@dataclass
class PlanStep:
    step_id: str = field(default_factory=lambda: f"step-{uuid.uuid4().hex[:8]}")
    capability: Capability = Capability.EXECUTE_LOCAL
    action: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    reasoning: str = ""
    estimated_cost_usd: float = 0.0
    estimated_duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "capability": self.capability.value,
            "action": self.action,
            "params": self.params,
            "depends_on": self.depends_on,
            "reasoning": self.reasoning,
            "estimated_cost_usd": self.estimated_cost_usd,
            "estimated_duration_seconds": self.estimated_duration_seconds,
        }


@dataclass
class Plan:
    plan_id: str = field(default_factory=lambda: f"plan-{uuid.uuid4().hex[:8]}")
    objective_id: str = ""
    steps: List[PlanStep] = field(default_factory=list)
    summary: str = ""
    risk_level: str = "low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "objective_id": self.objective_id,
            "steps": [s.to_dict() for s in self.steps],
            "summary": self.summary,
            "risk_level": self.risk_level,
        }


@dataclass
class ApprovalDecision:
    approval_ref: str = ""
    decision: str = "denied"  # allowed, denied, hitl
    reason: str = ""
    scope: str = "auto"  # auto, hitl
    approved_by: str = ""
    expires_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_ref": self.approval_ref,
            "decision": self.decision,
            "reason": self.reason,
            "scope": self.scope,
            "approved_by": self.approved_by,
            "expires_at": self.expires_at,
        }


@dataclass
class ExecutionResult:
    result_id: str = field(default_factory=lambda: f"res-{uuid.uuid4().hex[:8]}")
    step_id: str = ""
    status: str = "pending"
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    backend: str = ""
    trace_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "step_id": self.step_id,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "backend": self.backend,
            "trace_id": self.trace_id,
        }


@dataclass
class RuntimeTask:
    task_id: str = field(default_factory=lambda: f"task-{uuid.uuid4().hex[:8]}")
    objective_id: str = ""
    objective: Optional[Objective] = None
    plan: Optional[Plan] = None
    status: TaskStatus = TaskStatus.PENDING
    approvals: Dict[str, ApprovalDecision] = field(default_factory=dict)
    results: Dict[str, ExecutionResult] = field(default_factory=dict)
    completed_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    pending_steps: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    trace_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "objective_id": self.objective_id,
            "objective": self.objective.to_dict() if self.objective else None,
            "plan": self.plan.to_dict() if self.plan else None,
            "status": self.status.value,
            "approvals": {k: v.to_dict() for k, v in self.approvals.items()},
            "results": {k: v.to_dict() for k, v in self.results.items()},
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "pending_steps": self.pending_steps,
            "context": self.context,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "trace_id": self.trace_id,
        }
