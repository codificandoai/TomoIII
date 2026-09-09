"""
UC-703 — StackStorm Runtime Adapter.

Ejecuta playbooks/runbooks de infraestructura bajo autorización. Diferente del
adapter de incidentes (UC-075): este es un executor general del runtime AGI,
no solo para respuesta a incidentes.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class StackStormExecution:
    execution_id: str = field(default_factory=lambda: f"st2-exec-{uuid.uuid4().hex[:8]}")
    playbook: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    approval_ref: str = ""
    status: str = "pending"  # pending, running, succeeded, failed, timeout
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None


class StackStormRuntimeAdapter:
    """
    Adapter de StackStorm para ejecución de infra bajo UC-703.

    - Requiere `approval_ref` en cada ejecución.
    - Acepta un `allowlist` de playbooks para evitar ejecución arbitraria.
    - Simula respuestas cuando no hay servidor StackStorm real.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:9101",
        api_key: str = "",
        allowlist: Optional[List[str]] = None,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.allowlist = allowlist or [
            "remediate_disk_full",
            "restart_service",
            "scale_out_k8s",
            "block_ip",
            "notify_ops_channel",
        ]
        self._executions: Dict[str, StackStormExecution] = {}
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        self._handlers["remediate_disk_full"] = lambda p: {"cleaned_mb": 1024, "path": p.get("path", "/")}
        self._handlers["restart_service"] = lambda p: {"service": p.get("service"), "restarted": True}
        self._handlers["scale_out_k8s"] = lambda p: {"deployment": p.get("deployment"), "replicas": p.get("replicas", 3)}
        self._handlers["block_ip"] = lambda p: {"ip": p.get("ip"), "blocked": True}
        self._handlers["notify_ops_channel"] = lambda p: {"channel": p.get("channel"), "notified": True}

    def register_handler(self, playbook: str, fn: Callable[[Dict[str, Any]], Any]) -> None:
        self._handlers[playbook] = fn

    def execute(
        self,
        playbook: str,
        params: Dict[str, Any],
        approval_ref: str,
    ) -> StackStormExecution:
        if not approval_ref:
            return StackStormExecution(
                playbook=playbook,
                params=params,
                status="failed",
                error="Missing approval_ref",
            )
        if playbook not in self.allowlist:
            return StackStormExecution(
                playbook=playbook,
                params=params,
                approval_ref=approval_ref,
                status="failed",
                error=f"Playbook {playbook} not in allowlist",
            )
        execution = StackStormExecution(
            playbook=playbook,
            params=params,
            approval_ref=approval_ref,
            status="running",
        )
        self._executions[execution.execution_id] = execution
        handler = self._handlers.get(playbook)
        try:
            execution.result = handler(params) if handler else {"simulated": True}
            execution.status = "succeeded"
        except Exception as exc:
            execution.status = "failed"
            execution.error = str(exc)
        execution.finished_at = time.time()
        return execution

    def get_execution(self, execution_id: str) -> Optional[StackStormExecution]:
        return self._executions.get(execution_id)

    def list_executions(self, playbook: Optional[str] = None, status: Optional[str] = None) -> List[StackStormExecution]:
        executions = list(self._executions.values())
        if playbook:
            executions = [e for e in executions if e.playbook == playbook]
        if status:
            executions = [e for e in executions if e.status == status]
        return executions
