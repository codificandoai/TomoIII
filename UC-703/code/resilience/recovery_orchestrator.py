"""Orquestador de recuperación multi-paso para invocaciones de herramientas LLM."""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from resilience.escalation_chain import EscalationChain
from resilience.error_classifier import ErrorClassifier
from resilience.models_resilience import (
    RecoveryReport,
    ResilientPlanState,
    RetryPolicy,
    ToolCall,
    ToolResult,
)
from resilience.replanning import ContextRebuilder, ReplanningAgent
from resilience.retry_manager import RetryManager
from resilience.schema_validator import SchemaValidator
from resilience.telemetry_exporter import RecoveryTelemetryExporter


class RecoveryOrchestrator:
    """
    Envuelve cada invocación de herramienta con validación de esquema,
    clasificación de error, reintentos, replanificación semántica y escalación
    progresiva. No invalida pasos completados previos.
    """

    def __init__(
        self,
        validator: Optional[SchemaValidator] = None,
        retry_manager: Optional[RetryManager] = None,
        context_rebuilder: Optional[ContextRebuilder] = None,
        replanner: Optional[ReplanningAgent] = None,
        escalation: Optional[EscalationChain] = None,
        telemetry: Optional[RecoveryTelemetryExporter] = None,
        tool_registry: Optional[List[str]] = None,
    ) -> None:
        self.validator = validator or SchemaValidator()
        self.retry_manager = retry_manager or RetryManager()
        self.context_rebuilder = context_rebuilder or ContextRebuilder()
        self.replanner = replanner or ReplanningAgent()
        self.escalation = escalation or EscalationChain()
        self.telemetry = telemetry or RecoveryTelemetryExporter()
        self.tool_registry = tool_registry or []
        self._reports: List[RecoveryReport] = []

    def register_tool(
        self,
        tool_name: str,
        input_schema: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.validator.register_tool(tool_name, input_schema, output_schema)
        if tool_name not in self.tool_registry:
            self.tool_registry.append(tool_name)

    def invoke(
        self,
        run_id: str,
        step_id: str,
        tool_name: str,
        fn: Callable[..., Any],
        params: Dict[str, Any],
        completed_steps: Optional[List[str]] = None,
        partial_state: Optional[Dict[str, Any]] = None,
    ) -> RecoveryReport:
        # Level 1: schema validation on input
        validation = self.validator.validate_input(tool_name, params)
        if not validation["valid"]:
            self.telemetry.log(
                run_id=run_id,
                step_id=step_id,
                tool_name=tool_name,
                event="schema_validation_failed",
                message="input schema validation failed",
                metadata={"errors": validation["errors"]},
            )
            result = ToolResult(
                step_id=step_id,
                status="failed",
                error=f"input schema validation failed: {validation['errors']}",
                error_category="invalid_response",
                backend=tool_name,
            )
            self.telemetry.record_tool_result(result)
            return self._build_report(run_id, step_id, tool_name, result)

        # Level 2: execute with retries
        result = self.retry_manager.execute(step_id, tool_name, fn, **params)
        result.backend = tool_name
        self.telemetry.record_tool_result(result)
        self.telemetry.log(
            run_id=run_id,
            step_id=step_id,
            tool_name=tool_name,
            event="attempt" if result.status == "succeeded" else "retry_exhausted",
            error_category=result.error_category,
            message=result.error or "success",
            metadata={"attempts": result.attempts},
        )

        if result.status == "succeeded":
            # Validate output schema
            output_validation = self.validator.validate_output(tool_name, result.output)
            if not output_validation["valid"]:
                result.status = "failed"
                result.error = f"output schema validation failed: {output_validation['errors']}"
                result.error_category = "invalid_response"
                self.telemetry.record_tool_result(result)
            else:
                return self._build_report(run_id, step_id, tool_name, result)

        # Level 3: replanning with semantic context
        classification = ErrorClassifier().classify(error_message=result.error)
        state = self.context_rebuilder.build_context(
            run_id=run_id,
            completed_steps=completed_steps or [],
            failed_step=step_id,
            partial_state=partial_state or {},
            classification=classification,
            tool_name=tool_name,
            error_message=result.error,
        )
        suggestion = self.replanner.suggest(state, self.tool_registry)

        # Try replanned execution once if alternative tool suggested
        if suggestion.strategy == "alternative_tool" and suggestion.suggested_tool:
            replanned_result = self.retry_manager.execute(
                step_id, suggestion.suggested_tool, fn, **params
            )
            replanned_result.backend = suggestion.suggested_tool
            self.telemetry.record_tool_result(replanned_result)
            if replanned_result.status == "succeeded":
                replanned_result.recovery_action = f"replan:{suggestion.strategy}"
                return self._build_report(
                    run_id, step_id, tool_name, replanned_result, suggestion=suggestion
                )
            result = replanned_result

        # Level 4: escalation chain (repair agent -> HITL)
        self.telemetry.log(
            run_id=run_id,
            step_id=step_id,
            tool_name=tool_name,
            event="escalate",
            error_category=result.error_category,
            message="entering escalation chain",
        )
        escalated = self.escalation.escalate(state, tool_name, fn, **params)
        escalated.backend = tool_name
        self.telemetry.record_tool_result(escalated)
        if escalated.status == "escalated":
            self.telemetry.record_escalation("hitl")
        elif escalated.status == "recovered":
            self.telemetry.record_escalation("repair")
        return self._build_report(run_id, step_id, tool_name, escalated, suggestion=suggestion)

    def _build_report(
        self,
        run_id: str,
        step_id: str,
        tool_name: str,
        result: ToolResult,
        suggestion: Optional[Any] = None,
    ) -> RecoveryReport:
        escalation = None
        if result.status == "escalated" and result.recovery_action.startswith("hitl_escalation:"):
            eid = result.recovery_action.split(":", 1)[1]
            for item in self.escalation.hitl._items:
                if item.escalation_id == eid:
                    escalation = item
                    break
        report = RecoveryReport(
            run_id=run_id,
            step_id=step_id,
            final_status=result.status,
            original_error=result.error,
            error_category=result.error_category,
            attempts=result.attempts,
            recovery_action=result.recovery_action,
            final_output=result.output,
            escalation=escalation,
            replan_suggestion=suggestion,
            telemetry=self.telemetry.to_dict(),
        )
        self._reports.append(report)
        return report

    def get_report(self, report_id: str) -> Optional[RecoveryReport]:
        for r in self._reports:
            if r.report_id == report_id:
                return r
        return None

    def list_reports(self) -> List[RecoveryReport]:
        return list(self._reports)

    def render_prometheus(self) -> str:
        return self.telemetry.render_prometheus()

    def get_logs(self) -> List[Dict[str, Any]]:
        return self.telemetry.get_logs()

    def decide_hitl(self, escalation_id: str, operator_decision: str) -> Optional[Any]:
        return self.escalation.hitl.decide(escalation_id, operator_decision)
