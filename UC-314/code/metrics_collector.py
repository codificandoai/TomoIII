"""UC-314 — Métricas Prometheus para el sistema neuro-simbólico y planificación.
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram


class UC314Metrics:
    """Expone métricas de planificación recursiva, causalidad y auditoría."""

    def __init__(self) -> None:
        self.plans_total = Counter("uc314_plans_total", "Planes generados", ["status"])
        self.plan_depth = Histogram("uc314_plan_depth", "Profundidad máxima del plan")
        self.plan_nodes_total = Histogram("uc314_plan_nodes_total", "Nodos totales del plan")
        self.executability_ratio = Gauge("uc314_plan_executability_ratio", "Ratio de hojas ejecutables")
        self.causal_consistency = Gauge("uc314_plan_causal_consistency", "Consistencia causal del plan")
        self.audit_score = Gauge("uc314_plan_audit_score", "Puntuación de auditoría del plan")
        self.root_causes_total = Counter("uc314_root_causes_total", "Rupturas analizadas", ["llm_scm_agreement"])
        self.trace_latency = Histogram("uc314_root_cause_trace_seconds", "Latencia del trazado causal")
        self.scm_interventions_total = Counter("uc314_scm_interventions_total", "Correcciones del SCM al LLM")

    def observe_plan(self, status: str, depth: int, nodes: int, executability: float, causal: float, score: float) -> None:
        self.plans_total.labels(status=status).inc()
        self.plan_depth.observe(depth)
        self.plan_nodes_total.observe(nodes)
        self.executability_ratio.set(executability)
        self.causal_consistency.set(causal)
        self.audit_score.set(score)

    def observe_root_cause(self, agreement: bool, latency_seconds: float, intervention: bool) -> None:
        label = "agree" if agreement else "disagree"
        self.root_causes_total.labels(llm_scm_agreement=label).inc()
        self.trace_latency.observe(latency_seconds)
        if intervention:
            self.scm_interventions_total.inc()


metrics = UC314Metrics()
