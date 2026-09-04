"""UC-314 — Orquestador Neuro-Simbólico.

Combina el Modelo Causal Simbólico (SCM) con el planificador recursivo y el
simulador LLM. Permite trazar causas raíz de rupturas y validar planes contra
el grafo causal.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from causal_model import LLMReasoner, SymbolicCausalModel
from metrics_collector import metrics
from plan_evaluator import PlanEvaluator
from recursive_planner import PlanNode, RecursivePlanner
from tool_registry import ToolRegistry, default_tools


class NeuroSymbolicIntegrator:
    """Orquesta LLM + SCM para depuración causal y planificación segura."""

    def __init__(
        self,
        scm: Optional[SymbolicCausalModel] = None,
        llm: Optional[LLMReasoner] = None,
        tool_registry: Optional[ToolRegistry] = None,
        planner: Optional[RecursivePlanner] = None,
        evaluator: Optional[PlanEvaluator] = None,
    ) -> None:
        self.scm = scm or SymbolicCausalModel()
        self.llm = llm or LLMReasoner()
        self.registry = tool_registry or ToolRegistry(default_tools())
        self.planner = planner or RecursivePlanner(self.registry, self.scm, llm=self.llm)
        self.evaluator = evaluator or PlanEvaluator()

    def handle_breakdown(
        self,
        task_id: str,
        failed_tool: str,
        error_msg: str,
        context: str,
    ) -> Dict[str, Any]:
        """Recibe una ruptura, obtiene hipótesis del LLM y la contrasta con el SCM."""
        start = time.time()
        metrics.root_causes_total.labels(llm_scm_agreement="pending").inc()

        llm_hypothesis = self.llm.abstract_hypothesis(error_msg, context)
        formal_trace = self.scm.find_symbolic_root_cause(failed_tool)
        llm_guess = llm_hypothesis.get("proposed_root_cause")
        actual_root = formal_trace[-1] if len(formal_trace) > 1 else failed_tool
        agreement = bool(llm_guess == actual_root and llm_hypothesis.get("confidence", 0) > 0.8)
        intervention = not agreement and llm_guess is not None
        latency = time.time() - start
        metrics.observe_root_cause(agreement, latency, intervention)

        return {
            "task_id": task_id,
            "failed_tool": failed_tool,
            "error_msg": error_msg,
            "llm_hypothesis": llm_hypothesis,
            "formal_causal_trace": formal_trace,
            "actual_root_cause": actual_root,
            "llm_scm_agreement": agreement,
            "scm_intervention": intervention,
            "latency_seconds": round(latency, 4),
        }

    def plan_and_evaluate(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Genera un plan recursivo, lo evalúa y registra métricas."""
        root = self.planner.plan(goal, context)
        metrics.plans_total.labels(status="generated").inc()
        eval_metrics = self.evaluator.evaluate(root)
        metrics.observe_plan(
            status=root.status,
            depth=eval_metrics.max_depth,
            nodes=eval_metrics.total_nodes,
            executability=eval_metrics.executability_ratio,
            causal=eval_metrics.causal_consistency,
            score=eval_metrics.audit_score,
        )
        return {
            "goal": goal,
            "plan": root.to_dict(),
            "metrics": eval_metrics.to_dict(),
        }

    def execute_plan(self, goal: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Genera el plan, lo ejecuta simuladamente y evalúa el resultado."""
        result = self.plan_and_evaluate(goal, context)
        root = self.planner.plan(goal, context)
        executed_root = self.planner.execute_plan(root)
        final_metrics = self.evaluator.evaluate(executed_root)
        metrics.plans_total.labels(status=executed_root.status).inc()
        return {
            "goal": goal,
            "plan": executed_root.to_dict(),
            "metrics": final_metrics.to_dict(),
        }
