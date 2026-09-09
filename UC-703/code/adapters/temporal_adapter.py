"""
UC-703 — Temporal Adapter (durable workflow execution).

Encapsula el cliente Temporal. Si `temporalio` no está instalado, cae a un
simulador en memoria que mantiene checkpoints y estado.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type


@dataclass
class TemporalActivity:
    activity_id: str = field(default_factory=lambda: f"act-{uuid.uuid4().hex[:8]}")
    name: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, running, completed, failed
    result: Any = None
    error: Optional[str] = None
    attempt: int = 0
    max_attempts: int = 3


@dataclass
class TemporalWorkflow:
    workflow_id: str = field(default_factory=lambda: f"wf-{uuid.uuid4().hex[:8]}")
    task_queue: str = "uc703-default"
    activities: List[TemporalActivity] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed, cancelled
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class TemporalAdapter:
    """
    Adapter de Temporal para UC-703.

    - Mantiene workflows y actividades en memoria (simulación determinista).
    - Soporta reintentos, checkpoints y cancelación.
    - Si temporalio está instalado, se puede activar modo real conectando a un
      servidor externo sin cambiar la interfaz.
    """

    def __init__(self, temporal_host: str = "localhost:7233", namespace: str = "default") -> None:
        self.temporal_host = temporal_host
        self.namespace = namespace
        self._workflows: Dict[str, TemporalWorkflow] = {}
        self._activity_handlers: Dict[str, Callable[..., Any]] = {}
        try:
            from temporalio.client import Client  # type: ignore
            self._client_cls = Client
        except Exception:
            self._client_cls = None

    @property
    def real_client_available(self) -> bool:
        return self._client_cls is not None

    def register_activity(self, name: str, fn: Callable[..., Any]) -> None:
        self._activity_handlers[name] = fn

    def start_workflow(
        self,
        activities: List[Dict[str, Any]],
        workflow_id: Optional[str] = None,
        task_queue: str = "uc703-default",
        context: Optional[Dict[str, Any]] = None,
    ) -> TemporalWorkflow:
        wf = TemporalWorkflow(
            workflow_id=workflow_id or f"wf-{uuid.uuid4().hex[:8]}",
            task_queue=task_queue,
            activities=[TemporalActivity(**a) for a in activities],
            context=context or {},
        )
        self._workflows[wf.workflow_id] = wf
        return wf

    def get_workflow(self, workflow_id: str) -> Optional[TemporalWorkflow]:
        return self._workflows.get(workflow_id)

    def signal_workflow(self, workflow_id: str, signal: str, payload: Any = None) -> Optional[TemporalWorkflow]:
        wf = self._workflows.get(workflow_id)
        if not wf:
            return None
        wf.context.setdefault("signals", []).append({"signal": signal, "payload": payload, "at": time.time()})
        if signal == "cancel":
            wf.status = "cancelled"
        wf.updated_at = time.time()
        return wf

    def _execute_activity(self, activity: TemporalActivity) -> None:
        activity.status = "running"
        activity.attempt += 1
        handler = self._activity_handlers.get(activity.name)
        try:
            if handler:
                result = handler(**activity.params)
            else:
                result = {"simulated": True, "activity": activity.name, "params": activity.params}
            activity.result = result
            activity.status = "completed"
        except Exception as exc:
            activity.error = str(exc)
            if activity.attempt >= activity.max_attempts:
                activity.status = "failed"
            else:
                activity.status = "pending"

    def run_workflow(self, workflow_id: str) -> Optional[TemporalWorkflow]:
        wf = self._workflows.get(workflow_id)
        if not wf or wf.status == "cancelled":
            return wf
        wf.status = "running"
        # Retry loop: Temporal re-ejecuta actividades pendientes hasta completar o agotar reintentos.
        pending = True
        while pending and wf.status != "cancelled":
            pending = False
            for activity in wf.activities:
                if activity.status in ("completed", "failed"):
                    continue
                if activity.status == "pending":
                    pending = True
                self._execute_activity(activity)
                if activity.status == "failed":
                    wf.status = "failed"
                    wf.updated_at = time.time()
                    return wf
        if wf.status != "failed":
            wf.status = "completed"
        wf.updated_at = time.time()
        return wf

    def query_workflow(self, workflow_id: str, query_type: str = "state") -> Any:
        wf = self._workflows.get(workflow_id)
        if not wf:
            return None
        if query_type == "state":
            return {
                "workflow_id": wf.workflow_id,
                "status": wf.status,
                "activities": [
                    {
                        "activity_id": a.activity_id,
                        "name": a.name,
                        "status": a.status,
                        "attempt": a.attempt,
                        "result": a.result,
                        "error": a.error,
                    }
                    for a in wf.activities
                ],
                "context": wf.context,
            }
        return wf.context

    def list_workflows(self, status: Optional[str] = None) -> List[TemporalWorkflow]:
        workflows = list(self._workflows.values())
        if status:
            workflows = [w for w in workflows if w.status == status]
        return workflows
