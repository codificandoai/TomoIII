"""UC-700 — Agente de análisis de impacto.

Paso 3: Determinar su alcance.
"""

from __future__ import annotations

from typing import List, Optional

from models import Diagnosis, ImpactReport, Node, TrainingJob
from topology_graph import TopologyGraph


class ImpactAnalysisAgent:
    """Paso 3: Determinar el alcance del fallo usando el grafo de topología."""

    def __init__(self, graph: TopologyGraph):
        self.graph = graph

    def analyze(
        self,
        node: Node,
        diagnosis: Diagnosis,
        severity: str,
    ) -> ImpactReport:
        scope, affected_nodes, affected_devices = self.graph.get_scope(
            node.id, diagnosis.suspected_devices
        )

        # Si la severidad es S4 o S3 forzamos expansión de scope
        if severity == "S4":
            scope = "domain"
            affected_nodes = [n.id for n in self.graph.nodes.values() if n.zone == node.zone]
        elif severity == "S3" and scope == "device":
            scope = "node"
            affected_nodes = [node.id]

        job_map = self.graph.affected_workloads(affected_nodes, affected_devices)
        affected_jobs = list(job_map.keys())

        affected_tenants: List[str] = []
        affected_models: List[str] = []
        for job_id in affected_jobs:
            job = self.graph.jobs.get(job_id)
            if job:
                affected_tenants.append(job.name.split("/")[0] if "/" in job.name else "default")
                affected_models.append(job.name)

        blast_radius = self._blast_radius(scope, len(affected_nodes), len(affected_devices), len(affected_jobs))

        return ImpactReport(
            scope=scope,
            affected_nodes=affected_nodes,
            affected_devices=affected_devices,
            affected_jobs=affected_jobs,
            affected_tenants=list(set(affected_tenants)),
            affected_models=list(set(affected_models)),
            blast_radius_score=round(blast_radius, 4),
        )

    def _blast_radius(self, scope: str, nodes: int, devices: int, jobs: int) -> float:
        base = {"device": 0.1, "node": 0.3, "rack": 0.5, "zone": 0.7, "domain": 0.9, "region": 1.0}
        score = base.get(scope, 0.1)
        score += min(0.3, nodes * 0.05)
        score += min(0.2, devices * 0.02)
        return min(1.0, score)
