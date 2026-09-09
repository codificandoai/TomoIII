"""Cadena de escalación: agente reparador + cola HITL."""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from resilience.models_resilience import (
    EscalationRecord,
    ResilientPlanState,
    ToolResult,
)


class RepairAgent:
    """
    Subsistema especializado que intenta diagnosticar y corregir un fallo
    sin intervención humana.
    """

    def __init__(self, diagnostic_tools: Optional[Dict[str, Callable[..., Any]]] = None) -> None:
        self.diagnostic_tools = diagnostic_tools or {}

    def attempt_repair(
        self,
        state: ResilientPlanState,
        original_tool: str,
        original_fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> ToolResult:
        # First try with reduced parameters if possible
        if "verbose" in kwargs:
            kwargs.pop("verbose")
        if "retries" in kwargs:
            kwargs.pop("retries")
        try:
            output = original_fn(*args, **kwargs)
            return ToolResult(
                step_id=state.failed_step,
                status="recovered",
                output=output,
                recovery_action="repair_agent_sanitized_params",
                backend=original_tool,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                step_id=state.failed_step,
                status="failed",
                error=str(exc),
                recovery_action="repair_agent_failed",
                backend=original_tool,
            )


class HITLQueue:
    """
    Cola de aprobación humana con contexto completo del plan fallido.
    """

    def __init__(self) -> None:
        self._items: List[EscalationRecord] = []

    def request_review(
        self,
        step_id: str,
        context_summary: Dict[str, Any],
    ) -> EscalationRecord:
        record = EscalationRecord(
            step_id=step_id,
            level="hitl",
            status="pending",
            context_summary=context_summary,
        )
        self._items.append(record)
        return record

    def decide(
        self,
        escalation_id: str,
        operator_decision: str,
    ) -> Optional[EscalationRecord]:
        for item in self._items:
            if item.escalation_id == escalation_id:
                item.operator_decision = operator_decision
                item.status = "resolved" if operator_decision in ("continue", "retry", "approve") else "rejected"
                item.timestamp = time.time()
                return item
        return None

    def list_pending(self) -> List[EscalationRecord]:
        return [i for i in self._items if i.status == "pending"]


class EscalationChain:
    """
    Cadena de responsabilidad: primero reparador, luego HITL.
    """

    def __init__(
        self,
        repair_agent: Optional[RepairAgent] = None,
        hitl_queue: Optional[HITLQueue] = None,
    ) -> None:
        self.repair = repair_agent or RepairAgent()
        self.hitl = hitl_queue or HITLQueue()

    def escalate(
        self,
        state: ResilientPlanState,
        original_tool: str,
        original_fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> ToolResult:
        repair_result = self.repair.attempt_repair(state, original_tool, original_fn, *args, **kwargs)
        if repair_result.status == "recovered":
            return ToolResult(
                step_id=state.failed_step,
                status="recovered",
                output=repair_result.output,
                recovery_action="repair_agent",
                backend=original_tool,
            )
        record = self.hitl.request_review(
            step_id=state.failed_step,
            context_summary=state.to_dict(),
        )
        return ToolResult(
            step_id=state.failed_step,
            status="escalated",
            error="Awaiting HITL decision",
            recovery_action=f"hitl_escalation:{record.escalation_id}",
            backend=original_tool,
        )
