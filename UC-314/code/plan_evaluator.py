"""UC-314 — Evaluador y auditor de planes recursivos.

Calcula métricas de calidad del plan: profundidad, ejecutabilidad, cobertura,
coherencia causal, coste y latencia estimados, y emite un informe auditable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from recursive_planner import PlanNode


@dataclass
class PlanMetrics:
    total_nodes: int = 0
    executable_leaves: int = 0
    blocked_leaves: int = 0
    max_depth: int = 0
    executability_ratio: float = 0.0
    causal_consistency: float = 1.0
    estimated_cost: float = 0.0
    estimated_latency_ms: float = 0.0
    audit_score: float = 0.0
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_nodes": self.total_nodes,
            "executable_leaves": self.executable_leaves,
            "blocked_leaves": self.blocked_leaves,
            "max_depth": self.max_depth,
            "executability_ratio": round(self.executability_ratio, 3),
            "causal_consistency": round(self.causal_consistency, 3),
            "estimated_cost": round(self.estimated_cost, 3),
            "estimated_latency_ms": round(self.estimated_latency_ms, 3),
            "audit_score": round(self.audit_score, 3),
            "recommendations": self.recommendations,
        }


class PlanEvaluator:
    """Audita un plan recursivo generado por `RecursivePlanner`."""

    def __init__(self, cost_per_tool: float = 1.0, latency_ms_per_tool: float = 100.0) -> None:
        self.cost_per_tool = cost_per_tool
        self.latency_ms_per_tool = latency_ms_per_tool

    def evaluate(self, node: PlanNode) -> PlanMetrics:
        metrics = PlanMetrics()
        leaves: List[PlanNode] = []
        PlanEvaluator._collect_leaves(node, leaves)
        metrics.total_nodes = PlanEvaluator._count_nodes(node)
        metrics.max_depth = PlanEvaluator._max_depth(node)
        metrics.executable_leaves = sum(1 for leaf in leaves if leaf.status in ("executable", "executed"))
        metrics.blocked_leaves = sum(1 for leaf in leaves if leaf.status == "blocked")
        total_leaves = len(leaves) or 1
        metrics.executability_ratio = metrics.executable_leaves / total_leaves

        causal_issues = self._count_causal_blocks(node)
        if metrics.blocked_leaves:
            metrics.causal_consistency = 1.0 - (causal_issues / metrics.blocked_leaves)
        else:
            metrics.causal_consistency = 1.0

        metrics.estimated_cost = metrics.executable_leaves * self.cost_per_tool
        metrics.estimated_latency_ms = metrics.executable_leaves * self.latency_ms_per_tool

        metrics.audit_score = self._audit_score(metrics)
        metrics.recommendations = self._recommendations(metrics)
        return metrics

    @staticmethod
    def _collect_leaves(node: PlanNode, leaves: List[PlanNode]) -> None:
        if not node.children:
            leaves.append(node)
            return
        for child in node.children:
            PlanEvaluator._collect_leaves(child, leaves)

    @staticmethod
    def _count_nodes(node: PlanNode) -> int:
        return 1 + sum(PlanEvaluator._count_nodes(c) for c in node.children)

    @staticmethod
    def _max_depth(node: PlanNode) -> int:
        if not node.children:
            return node.depth
        return max(PlanEvaluator._max_depth(c) for c in node.children)

    def _count_causal_blocks(self, node: PlanNode) -> int:
        count = 0
        if node.status == "blocked" and node.audit.get("stop_reason") == "causal_dependency_failure":
            count += 1
        for child in node.children:
            count += self._count_causal_blocks(child)
        return count

    @staticmethod
    def _audit_score(metrics: PlanMetrics) -> float:
        score = 0.0
        score += min(0.4, metrics.executability_ratio * 0.4)
        score += min(0.3, metrics.causal_consistency * 0.3)
        depth_penalty = max(0, metrics.max_depth - 5) * 0.05
        score += max(0, 0.3 - depth_penalty)
        return max(0.0, min(1.0, score))

    @staticmethod
    def _recommendations(metrics: PlanMetrics) -> List[str]:
        recs = []
        if metrics.executability_ratio < 1.0:
            missing = metrics.blocked_leaves
            recs.append(f"{missing} subtarea(s) no son ejecutables; registrar nuevas herramientas o ajustar el alcance.")
        if metrics.causal_consistency < 1.0:
            recs.append("Existen bloqueos causales; revisar dependencias del SCM antes de ejecutar.")
        if metrics.max_depth > 5:
            recs.append("Plan demasiado profundo; considere simplificar la descomposición.")
        if metrics.audit_score >= 0.9:
            recs.append("Plan de alta calidad; apto para ejecución.")
        return recs
