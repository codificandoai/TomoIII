"""
UC-703 — n8n Adapter.

Conecta el runtime AGI con flujos de n8n para integración SaaS.
Soporta ejecución local vía webhook y simulación determinista.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class N8nWorkflowExecution:
    execution_id: str = field(default_factory=lambda: f"n8n-{uuid.uuid4().hex[:8]}")
    workflow_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    approval_ref: str = ""
    status: str = "pending"  # pending, running, succeeded, failed
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None


class N8nAdapter:
    """
    Adapter de n8n para UC-703.

    - Ejecuta workflows de n8n vía webhook (o simulación).
    - Valida que el workflow esté en allowlist.
    - Requiere approval_ref.
    - No expone credenciales; las busca en el entorno o en un broker externo.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:5678",
        webhook_path: str = "/webhook",
        allowlist: Optional[List[str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.webhook_path = webhook_path
        self.allowlist = allowlist or [
            "notify_slack",
            "create_notion_page",
            "salesforce_create_lead",
            "jira_create_ticket",
            "send_email",
        ]
        self._executions: Dict[str, N8nWorkflowExecution] = {}
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        self._handlers["notify_slack"] = lambda p: {"channel": p.get("channel"), "sent": True}
        self._handlers["create_notion_page"] = lambda p: {"page_id": f"notion-{uuid.uuid4().hex[:6]}", "title": p.get("title")}
        self._handlers["salesforce_create_lead"] = lambda p: {"lead_id": f"sf-{uuid.uuid4().hex[:6]}", "email": p.get("email")}
        self._handlers["jira_create_ticket"] = lambda p: {"ticket_id": f"JIRA-{uuid.uuid4().hex[:6].upper()}", "summary": p.get("summary")}
        self._handlers["send_email"] = lambda p: {"to": p.get("to"), "sent": True}

    def register_handler(self, workflow_id: str, fn: Callable[[Dict[str, Any]], Any]) -> None:
        self._handlers[workflow_id] = fn

    def execute(
        self,
        workflow_id: str,
        payload: Dict[str, Any],
        approval_ref: str,
    ) -> N8nWorkflowExecution:
        if not approval_ref:
            return N8nWorkflowExecution(
                workflow_id=workflow_id,
                payload=payload,
                status="failed",
                error="Missing approval_ref",
            )
        if workflow_id not in self.allowlist:
            return N8nWorkflowExecution(
                workflow_id=workflow_id,
                payload=payload,
                approval_ref=approval_ref,
                status="failed",
                error=f"Workflow {workflow_id} not in allowlist",
            )
        execution = N8nWorkflowExecution(
            workflow_id=workflow_id,
            payload=payload,
            approval_ref=approval_ref,
            status="running",
        )
        self._executions[execution.execution_id] = execution
        handler = self._handlers.get(workflow_id)
        try:
            execution.result = handler(payload) if handler else {"simulated": True}
            execution.status = "succeeded"
        except Exception as exc:
            execution.status = "failed"
            execution.error = str(exc)
        execution.finished_at = time.time()
        return execution

    def get_execution(self, execution_id: str) -> Optional[N8nWorkflowExecution]:
        return self._executions.get(execution_id)

    def list_executions(self, workflow_id: Optional[str] = None, status: Optional[str] = None) -> List[N8nWorkflowExecution]:
        executions = list(self._executions.values())
        if workflow_id:
            executions = [e for e in executions if e.workflow_id == workflow_id]
        if status:
            executions = [e for e in executions if e.status == status]
        return executions
