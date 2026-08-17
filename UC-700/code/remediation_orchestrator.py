"""UC-700 — Orquestador de remediación.

Pasos 5, 7: Reconfigurar el trabajo y reponer el componente defectuoso.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from config import AgentConfig, HealthState, RemediationStrategy, SeverityLevel
from models import (
    Checkpoint,
    Device,
    ImpactReport,
    Incident,
    Node,
    RemediationPlan,
    TrainingJob,
)


class RemediationOrchestrator:
    """Decide y ejecuta la estrategia de remediación con mínimo impacto."""

    def __init__(self, config: AgentConfig, checkpoint_manager, graph):
        self.config = config
        self.checkpoint_manager = checkpoint_manager
        self.graph = graph

    def build_plan(
        self,
        incident: Incident,
        node: Node,
        impact: ImpactReport,
        severity: str,
    ) -> RemediationPlan:
        strategy = self._select_strategy(incident.failure_class, severity, impact.scope)
        affected_jobs = impact.affected_jobs
        checkpoint_id: Optional[str] = None
        replacement_node_id: Optional[str] = None

        if strategy in (RemediationStrategy.ELASTIC_TRAINING, RemediationStrategy.CHECKPOINT_RECOVERY, RemediationStrategy.REPLACE_NODE):
            job = self._primary_job(affected_jobs)
            if job:
                cp = self.checkpoint_manager.get_last_valid_checkpoint(job.id)
                if cp:
                    checkpoint_id = cp.id

        if strategy in (RemediationStrategy.REPLACE_NODE, RemediationStrategy.ELASTIC_TRAINING):
            replacement_node_id = self._find_replacement(node, severity)

        steps = self._build_steps(strategy, node, impact, checkpoint_id, replacement_node_id)

        return RemediationPlan(
            strategy=strategy,
            target_node_id=node.id,
            target_device_ids=impact.affected_devices,
            affected_jobs=affected_jobs,
            checkpoint_id=checkpoint_id,
            replacement_node_id=replacement_node_id,
            requires_approval=severity in self.config.require_human_approval,
            estimated_downtime_sec=self._estimate_downtime(strategy),
            steps=steps,
        )

    def _select_strategy(self, failure_class: str, severity: str, scope: str) -> str:
        if severity == SeverityLevel.S0:
            return RemediationStrategy.ADJUST_LOAD
        if severity == SeverityLevel.S1:
            return RemediationStrategy.QUARANTINE_DEVICE
        if severity == SeverityLevel.S4:
            return RemediationStrategy.DOMAIN_FAILOVER
        if scope in ("device",) and severity == SeverityLevel.S2:
            return RemediationStrategy.ELASTIC_TRAINING
        if scope in ("node", "rack"):
            if failure_class in ("HARDWARE", "THERMAL"):
                return RemediationStrategy.REPLACE_NODE
            return RemediationStrategy.CHECKPOINT_RECOVERY
        return RemediationStrategy.CHECKPOINT_RECOVERY

    def _primary_job(self, job_ids: List[str]) -> Optional[TrainingJob]:
        for job_id in job_ids:
            job = self.graph.jobs.get(job_id)
            if job:
                return job
        return None

    def _find_replacement(self, node: Node, severity: str) -> Optional[str]:
        """Selecciona nodo sano homólogo con menor riesgo predictivo."""
        candidates = [
            n
            for n in self.graph.nodes.values()
            if n.zone == node.zone and n.id != node.id and n.state == HealthState.HEALTHY
        ]
        if not candidates:
            candidates = [
                n
                for n in self.graph.nodes.values()
                if n.id != node.id and n.state in (HealthState.HEALTHY, HealthState.AVAILABLE)
            ]
        if candidates:
            # Preferir nodo con más GPUs libres (simulado)
            return max(candidates, key=lambda n: len(n.devices)).id
        return None

    def _build_steps(
        self,
        strategy: str,
        node: Node,
        impact: ImpactReport,
        checkpoint_id: Optional[str],
        replacement_node_id: Optional[str],
    ) -> List[Dict[str, any]]:
        steps: List[Dict[str, any]] = []
        steps.append({"order": 1, "action": "checkpoint", "detail": f"trigger checkpoint before remediation, cp={checkpoint_id}"})
        steps.append({"order": 2, "action": "isolate", "detail": f"cordon+drain {node.id}, quarantine devices {impact.affected_devices}"})
        if strategy == RemediationStrategy.ELASTIC_TRAINING:
            steps.append({"order": 3, "action": "reconfigure", "detail": "reduce world size and continue elastic training"})
        elif strategy == RemediationStrategy.REPLACE_NODE:
            steps.append({"order": 3, "action": "reprovision", "detail": f"boot replacement node {replacement_node_id}"})
            steps.append({"order": 4, "action": "rebuild", "detail": "reconstruct distributed group with new node"})
        elif strategy == RemediationStrategy.CHECKPOINT_RECOVERY:
            steps.append({"order": 3, "action": "restore", "detail": f"restart from checkpoint {checkpoint_id}"})
        elif strategy == RemediationStrategy.DOMAIN_FAILOVER:
            steps.append({"order": 3, "action": "failover", "detail": f"resume training in backup domain {self.config.backup_domain}"})
        steps.append({"order": 5, "action": "validate", "detail": "verify health, loss and throughput"})
        return steps

    def _estimate_downtime(self, strategy: str) -> float:
        estimates = {
            RemediationStrategy.NONE: 0.0,
            RemediationStrategy.ADJUST_LOAD: 5.0,
            RemediationStrategy.QUARANTINE_DEVICE: 30.0,
            RemediationStrategy.ELASTIC_TRAINING: 60.0,
            RemediationStrategy.CHECKPOINT_RECOVERY: 120.0,
            RemediationStrategy.REPLACE_NODE: 300.0,
            RemediationStrategy.DOMAIN_FAILOVER: 600.0,
        }
        return estimates.get(strategy, 60.0)

    def execute_plan(self, plan: RemediationPlan, incident: Incident) -> Dict[str, any]:
        """Simula ejecución del plan en dry-run."""
        executed = []
        for step in plan.steps:
            executed.append({"step": step, "status": "success", "latency_ms": 10})
        incident.state = HealthState.RECOVERING
        return {
            "strategy": plan.strategy,
            "target_node_id": plan.target_node_id,
            "checkpoint_id": plan.checkpoint_id,
            "replacement_node_id": plan.replacement_node_id,
            "executed_steps": executed,
            "estimated_downtime_sec": plan.estimated_downtime_sec,
            "requires_approval": plan.requires_approval,
        }
