"""Reconstrucción del contexto y replanificación semántica de pasos fallidos."""
from __future__ import annotations

from typing import Any, Dict, List

from resilience.models_resilience import (
    ErrorClassification,
    ReplanSuggestion,
    ResilientPlanState,
)


class ContextRebuilder:
    """
    Construye una traza comprimida del plan: pasos completados, estado parcial
    y causa raíz, para alimentar un agente de replanificación.
    """

    def build_context(
        self,
        run_id: str,
        completed_steps: List[str],
        failed_step: str,
        partial_state: Dict[str, Any],
        classification: ErrorClassification,
        tool_name: str,
        error_message: str,
    ) -> ResilientPlanState:
        fallback_prompt = (
            f"Plan {run_id}: steps completed so far: {completed_steps}. "
            f"Step {failed_step} failed in tool {tool_name} with {classification.category}: {error_message}. "
            f"Root cause hint: {classification.root_cause_hint}. "
            "Consider: (1) alternative tool, (2) simplify objective, (3) split step."
        )
        return ResilientPlanState(
            run_id=run_id,
            completed_steps=list(completed_steps),
            failed_step=failed_step,
            partial_state=dict(partial_state),
            root_cause=classification.root_cause_hint,
            fallback_prompt=fallback_prompt,
        )


class ReplanningAgent:
    """
    Genera sugerencias de replanificación semántica ante un paso fallido.
    """

    def suggest(self, state: ResilientPlanState, tool_registry: List[str]) -> ReplanSuggestion:
        if "timeout" in state.root_cause or "rate" in state.root_cause:
            strategy = "alternative_tool"
            reasoning = "Tool timing/rate issue; retry with similar capability tool."
            suggested_tool = next((t for t in tool_registry if t != state.failed_step), "")
        elif "context" in state.root_cause:
            strategy = "simplify"
            reasoning = "Context too long; reduce objective scope or summarize."
            suggested_tool = "summarize_context"
        elif "invalid" in state.root_cause or "schema" in state.root_cause:
            strategy = "split"
            reasoning = "Output malformed; split step into smaller validation units."
            suggested_tool = "validate_and_retry"
        else:
            strategy = "escalate"
            reasoning = "Unhandled failure pattern; escalate to repair agent/HITL."
            suggested_tool = "escalate"
        return ReplanSuggestion(
            step_id=state.failed_step,
            strategy=strategy,
            reasoning=reasoning,
            suggested_tool=suggested_tool,
            suggested_params={"partial_state": state.partial_state, "root_cause": state.root_cause},
        )
