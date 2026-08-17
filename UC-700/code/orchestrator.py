"""UC-700 — Orquestador principal de autosanación avanzada del entrenamiento.

Coordina el pipeline completo de agentes:
  1. TelemetryAgent
  2. AnomalyDetectionAgent
  3. DiagnosticAgent
  4. ImpactAnalysisAgent
  5. IsolationAgent
  6. RemediationOrchestrator
  7. CheckpointManager
  8. ValidationAgent
  9. EfficiencyAgent
  10. EscalationAgent
  11. GovernanceAgent
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from anomaly_detection_agent import AnomalyDetectionAgent
from checkpoint_manager import CheckpointManager
from config import AgentConfig, FailureClass, HealthState, SeverityLevel
from diagnostic_agent import DiagnosticAgent
from efficiency_agent import EfficiencyAgent
from escalation_agent import EscalationAgent
from governance_agent import GovernanceAgent
from impact_analysis_agent import ImpactAnalysisAgent
from isolation_agent import IsolationAgent
from models import (
    Device,
    Incident,
    Node,
    TelemetrySnapshot,
    TrainingJob,
)
from remediation_orchestrator import RemediationOrchestrator
from telemetry_collector import TelemetryCollector
from topology_graph import TopologyGraph
from validation_agent import ValidationAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [UC-700] %(levelname)s — %(message)s",
)
logger = logging.getLogger("uc700")


class SelfHealingOrchestrator:
    """Orquesta el flujo agentic de autosanación."""

    def __init__(self, config: Optional[AgentConfig] = None, dry_run: bool = True):
        self.config = config or AgentConfig()
        self.dry_run = dry_run
        self.telemetry = TelemetryCollector()
        self.anomaly = AnomalyDetectionAgent(self.config)
        self.diagnostic = DiagnosticAgent(min_evidence_signals=self.config.min_evidence_signals)
        self.topology = TopologyGraph()
        self.impact = ImpactAnalysisAgent(self.topology)
        self.isolation = IsolationAgent(dry_run=dry_run)
        self.checkpoints = CheckpointManager(self.config)
        self.remediation = RemediationOrchestrator(self.config, self.checkpoints, self.topology)
        self.validation = ValidationAgent(self.config)
        self.efficiency = EfficiencyAgent(self.config)
        self.escalation = EscalationAgent(self.config)
        self.governance = GovernanceAgent()
        self.incidents: Dict[str, Incident] = {}

    def register_node(self, node: Node) -> None:
        self.topology.add_node(node)

    def register_job(self, job: TrainingJob) -> None:
        self.topology.add_job(job)

    def build_default_cluster(self) -> None:
        """Crea un cluster simulado para demostración."""
        for rack in ("R-A", "R-B"):
            for n in range(1, 5):
                node_id = f"N-{rack}-{n}"
                devices = [
                    Device(
                        id=f"{node_id}-gpu-0",
                        kind="gpu",
                        vendor="nvidia",
                        index=0,
                        node_id=node_id,
                        vram_total_gb=80.0,
                        vram_used_gb=60.0,
                        temperature_c=65.0,
                        util_pct=80.0,
                    ),
                    Device(
                        id=f"{node_id}-gpu-1",
                        kind="gpu",
                        vendor="nvidia",
                        index=1,
                        node_id=node_id,
                        vram_total_gb=80.0,
                        vram_used_gb=58.0,
                        temperature_c=62.0,
                        util_pct=78.0,
                    ),
                ]
                self.register_node(
                    Node(
                        id=node_id,
                        campus="CAMPUS-1",
                        zone="zone-a" if rack == "R-A" else "zone-b",
                        room="ROOM-1",
                        rack=rack,
                        devices=devices,
                    )
                )
        self.register_job(
            TrainingJob(
                id="train-llm-001",
                name="tenant-a/llm-pretrain-v2",
                replicas=8,
                nodes=[f"N-R-A-{n}" for n in range(1, 5)] + [f"N-R-B-{n}" for n in range(1, 5)],
                checkpoint_path="/data/checkpoints/train-llm-001",
                samples_per_sec_baseline=100000.0,
                loss_baseline=2.0,
            )
        )
        for step in range(0, 1000, 100):
            job = self.topology.jobs["train-llm-001"]
            self.checkpoints.create_checkpoint(job, global_step=step, size_bytes=45 * 1024 ** 3, verified=True)

    def run_pipeline(
        self,
        node_id: str,
        device_id: Optional[str] = None,
        inject_failure: bool = False,
        operator_id: Optional[str] = None,
    ) -> Incident:
        """Ejecuta el pipeline completo de autosanación sobre un nodo."""
        node = self.topology.nodes.get(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not registered")

        device = next((d for d in node.devices if d.id == device_id), None) if device_id else None

        # 1. Recolectar telemetría
        snapshot = self.telemetry.collect_node(node, device=device, inject_failure=inject_failure)
        if inject_failure:
            snapshot = self.telemetry.inject_memory_failure_signature(snapshot)

        incident = Incident(node_id=node_id, device_ids=[device.id] if device else [])
        self.incidents[incident.id] = incident
        incident.add_trace("telemetry", "TelemetryCollector", {"metrics": snapshot.metrics, "events": snapshot.events})

        # 2. Detectar anomalía
        peers = [
            self.telemetry.collect_node(n, n.devices[0] if n.devices else None)
            for n in self.topology.get_homologous_nodes(node_id)
        ]
        signal = self.anomaly.detect(snapshot, peers=peers)
        if not signal:
            incident.state = HealthState.HEALTHY
            incident.add_trace("detection", "AnomalyDetectionAgent", {"result": "no_anomaly"})
            return incident

        incident.add_trace("detection", "AnomalyDetectionAgent", signal.__dict__)

        # 3. Clasificar severidad
        severity = self.anomaly.classify_severity(signal)
        incident.severity = severity
        incident.add_trace("severity", "AnomalyDetectionAgent", {"severity": severity})

        # 4. Diagnóstico
        diagnosis = self.diagnostic.diagnose(node, snapshot, signal)
        incident.diagnosis = diagnosis
        incident.failure_class = diagnosis.failure_class
        incident.device_ids = diagnosis.suspected_devices or incident.device_ids
        incident.add_trace("diagnosis", "DiagnosticAgent", diagnosis.__dict__)

        # 5. Impacto
        impact = self.impact.analyze(node, diagnosis, severity)
        incident.impact = impact
        incident.add_trace("impact", "ImpactAnalysisAgent", impact.__dict__)

        # 6. Aislamiento
        plan = self.remediation.build_plan(incident, node, impact, severity)
        incident.plan = plan
        approval = self.governance.approve_plan(incident, plan, operator_id=operator_id)
        incident.add_trace("governance", "GovernanceAgent", approval)

        if approval["approved"]:
            isolation_result = self.isolation.isolate(node, impact, plan)
            incident.add_trace("isolation", "IsolationAgent", isolation_result)

            # 7/5. Checkpoint y reconfiguración
            execution = self.remediation.execute_plan(plan, incident)
            incident.add_trace("remediation", "RemediationOrchestrator", execution)
        else:
            incident.escalated = True
            incident.add_trace("remediation", "RemediationOrchestrator", {"status": "pending_approval"})

        # 8. Validación
        job = self.topology.jobs.get(plan.affected_jobs[0]) if plan and plan.affected_jobs else None
        if job:
            # Simulamos snapshots post-remediación
            post_snapshots = [self.telemetry.collect_job(job, degraded=inject_failure) for _ in range(5)]
            validation = self.validation.validate(job, post_snapshots)
            incident.validation = validation
            incident.add_trace("validation", "ValidationAgent", validation)

            # 9. Eficiencia
            efficiency = self.efficiency.measure(job, post_snapshots)
            incident.efficiency = efficiency
            incident.add_trace("efficiency", "EfficiencyAgent", efficiency)

        # 10. Escalamiento / cierre
        resolution = self.escalation.evaluate(incident)
        incident.add_trace("resolution", "EscalationAgent", resolution)

        return incident

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        return self.incidents.get(incident_id)

    def list_incidents(self) -> List[Incident]:
        return list(self.incidents.values())
