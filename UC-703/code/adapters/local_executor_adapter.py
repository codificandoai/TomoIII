"""
UC-703 — Local Executor Adapter.

Ejecuta acciones locales delegando al kernel de agentes UC-317 o a un ejecutor
inyectado. Si no hay conexión real, simula la ejecución.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class LocalExecution:
    execution_id: str = field(default_factory=lambda: f"local-{uuid.uuid4().hex[:8]}")
    action: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    approval_ref: str = ""
    status: str = "pending"  # pending, running, succeeded, failed
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


class LocalExecutorAdapter:
    """
    Adapter de ejecución local para UC-703.

    - Recibe acciones y parámetros.
    - Verifica `approval_ref`.
    - Delega a `external_executor` si se provee (por ejemplo, UC-317 kernel).
    - Si no, ejecuta handlers registrados o simula.
    """

    def __init__(
        self,
        external_executor: Optional[Callable[[str, Dict[str, Any], str], Any]] = None,
    ) -> None:
        self.external_executor = external_executor
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self._executions: Dict[str, LocalExecution] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        self._handlers["llm_call"] = lambda p: {"model": p.get("model", "mock"), "output": "mock-llm-output"}
        self._handlers["search_memory"] = lambda p: {"hits": ["memory-1", "memory-2"]}
        self._handlers["store_memory"] = lambda p: {"stored": p.get("key"), "status": "ok"}
        self._handlers["tool_call"] = lambda p: {"tool": p.get("tool"), "output": "mock-tool-output"}

    def register_handler(self, action: str, fn: Callable[[Dict[str, Any]], Any]) -> None:
        self._handlers[action] = fn

    def execute(self, action: str, params: Dict[str, Any], approval_ref: str) -> LocalExecution:
        if not approval_ref:
            return LocalExecution(
                action=action,
                params=params,
                status="failed",
                error="Missing approval_ref",
            )
        execution = LocalExecution(
            action=action,
            params=params,
            approval_ref=approval_ref,
            status="running",
            started_at=time.time(),
        )
        self._executions[execution.execution_id] = execution
        try:
            if self.external_executor:
                execution.result = self.external_executor(action, params, approval_ref)
            elif action in self._handlers:
                execution.result = self._handlers[action](params)
            else:
                execution.result = {"simulated": True, "action": action, "params": params}
            execution.status = "succeeded"
        except Exception as exc:
            execution.status = "failed"
            execution.error = str(exc)
        execution.finished_at = time.time()
        return execution

    def get_execution(self, execution_id: str) -> Optional[LocalExecution]:
        return self._executions.get(execution_id)

    def list_executions(self, action: Optional[str] = None, status: Optional[str] = None) -> List[LocalExecution]:
        executions = list(self._executions.values())
        if action:
            executions = [e for e in executions if e.action == action]
        if status:
            executions = [e for e in executions if e.status == status]
        return executions
