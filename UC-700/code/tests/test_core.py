"""Pruebas unitarias del core de autosanación UC-700."""

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from anomaly_detection_agent import AnomalyDetectionAgent
from checkpoint_manager import CheckpointManager
from config import AgentConfig, FailureClass, HealthState, SeverityLevel
from diagnostic_agent import DiagnosticAgent
from efficiency_agent import EfficiencyAgent
from escalation_agent import EscalationAgent
from impact_analysis_agent import ImpactAnalysisAgent
from models import Device, Diagnosis, Node, TelemetrySnapshot, TrainingJob
from topology_graph import TopologyGraph
from validation_agent import ValidationAgent


class TestAnomalyDetectionAgent(unittest.TestCase):
    def setUp(self):
        self.config = AgentConfig()
        self.agent = AnomalyDetectionAgent(self.config)

    def _snapshot(self, temp: float = 40.0, vram_used: float = 10.0, vram_total: float = 80.0, xid: float = 0.0, util: float = 80.0) -> TelemetrySnapshot:
        return TelemetrySnapshot(
            node_id="N-TEST",
            timestamp=datetime.utcnow(),
            metrics={
                "DCGM_FI_DEV_GPU_TEMP": temp,
                "DCGM_FI_DEV_FB_USED": vram_used,
                "DCGM_FI_DEV_FB_TOTAL": vram_total,
                "DCGM_FI_DEV_XID_ERRORS": xid,
                "DCGM_FI_DEV_GPU_UTIL": util,
                "DCGM_FI_DEV_PCIE_REPLAY": 0.0,
                "node_network_transmit_drop_total": 0.0,
            },
        )

    def test_no_anomaly_on_healthy_node(self):
        snap = self._snapshot()
        for _ in range(5):
            signal = self.agent.detect(snap)
        self.assertIsNone(signal)

    def test_detects_memory_failure_signature(self):
        snap = self._snapshot(temp=98.0, vram_used=79.0, vram_total=80.0, xid=12.0, util=5.0)
        signal = self.agent.detect(snap)
        self.assertIsNotNone(signal)
        self.assertGreaterEqual(signal.score, self.config.thresholds.anomaly_score)
        self.assertIn("gpu_temp", " ".join(signal.contributing_metrics))

    def test_classify_severity(self):
        from models import AnomalySignal

        signal = AnomalySignal(
            node_id="N-TEST",
            score=0.96,
            features={"xid": 12.0},
            contributing_metrics=["xid_errors=12"],
            timestamp=datetime.utcnow(),
            confidence=0.95,
        )
        self.assertEqual(self.agent.classify_severity(signal), SeverityLevel.S3)


class TestDiagnosticAgent(unittest.TestCase):
    def setUp(self):
        self.agent = DiagnosticAgent(min_evidence_signals=1)
        self.node = Node(id="N-TEST", campus="C", zone="Z", room="R", rack="R-A", devices=[Device(id="N-TEST-gpu-0", kind="gpu", vendor="nvidia", index=0, node_id="N-TEST")])

    def test_diagnose_hardware_memory(self):
        snap = TelemetrySnapshot(
            node_id="N-TEST",
            timestamp=datetime.utcnow(),
            metrics={
                "DCGM_FI_DEV_GPU_TEMP": 95.0,
                "DCGM_FI_DEV_FB_USED": 79.0,
                "DCGM_FI_DEV_FB_TOTAL": 80.0,
                "DCGM_FI_DEV_XID_ERRORS": 8.0,
                "DCGM_FI_DEV_GPU_UTIL": 5.0,
                "DCGM_FI_DEV_PCIE_REPLAY": 80.0,
            },
        )
        from anomaly_detection_agent import AnomalySignal

        signal = AnomalySignal(
            node_id="N-TEST",
            score=0.9,
            features={"xid": 8.0, "temp": 1.2},
            contributing_metrics=["xid_errors=8"],
            timestamp=datetime.utcnow(),
            confidence=0.9,
        )
        diag = self.agent.diagnose(self.node, snap, signal)
        self.assertEqual(diag.failure_class, FailureClass.HARDWARE)
        self.assertGreaterEqual(diag.confidence, 0.5)


class TestImpactAnalysisAgent(unittest.TestCase):
    def setUp(self):
        self.graph = TopologyGraph()
        self.node = Node(id="N-1", campus="C", zone="Z", room="R", rack="R-A", devices=[Device(id="N-1-gpu-0", kind="gpu", vendor="nvidia", index=0, node_id="N-1")])
        self.graph.add_node(self.node)
        job = TrainingJob(id="j1", name="tenant-a/job", replicas=2, nodes=["N-1", "N-2"])
        self.graph.add_job(job)
        self.agent = ImpactAnalysisAgent(self.graph)

    def test_scope_device(self):
        diag = Diagnosis(failure_class=FailureClass.HARDWARE, evidence=[], confidence=0.8, suspected_devices=["N-1-gpu-0"])
        impact = self.agent.analyze(self.node, diag, SeverityLevel.S2)
        self.assertIn(impact.scope, ("device", "node"))
        self.assertIn("N-1", impact.affected_nodes)
        self.assertIn("j1", impact.affected_jobs)


class TestCheckpointManager(unittest.TestCase):
    def setUp(self):
        self.config = AgentConfig()
        self.cm = CheckpointManager(self.config, storage_path="/tmp/uc700-test-checkpoints")
        self.job = TrainingJob(id="j1", name="tenant-a/job", replicas=2, nodes=["N-1"])

    def test_create_and_restore(self):
        cp = self.cm.create_checkpoint(self.job, global_step=100, verified=True)
        self.assertTrue(cp.verified)
        last = self.cm.get_last_valid_checkpoint(self.job.id)
        self.assertEqual(last.id, cp.id)
        result = self.cm.restore(self.job, last)
        self.assertTrue(result["restored"])


class TestValidationAndEfficiency(unittest.TestCase):
    def setUp(self):
        self.config = AgentConfig()
        self.validator = ValidationAgent(self.config)
        self.eff = EfficiencyAgent(self.config)
        self.job = TrainingJob(id="j1", name="tenant-a/job", replicas=2, nodes=["N-1"], samples_per_sec_baseline=100000.0, loss_baseline=2.0)

    def test_validation_pass(self):
        snaps = [
            TelemetrySnapshot(node_id="N-1", timestamp=datetime.utcnow(), metrics={"training_loss": 2.01, "training_samples_per_sec": 98000, "training_step_time_ms": 120, "training_grad_norm": 1.5})
            for _ in range(5)
        ]
        result = self.validator.validate(self.job, snaps)
        self.assertTrue(result["valid"])

    def test_efficiency_acceptable(self):
        snaps = [TelemetrySnapshot(node_id="N-1", timestamp=datetime.utcnow(), metrics={"training_samples_per_sec": 96000, "training_step_time_ms": 125}) for _ in range(5)]
        result = self.eff.measure(self.job, snaps)
        self.assertEqual(result["efficiency_pct"], 96.0)
        self.assertTrue(result["acceptable"])

    def test_efficiency_unacceptable(self):
        snaps = [TelemetrySnapshot(node_id="N-1", timestamp=datetime.utcnow(), metrics={"training_samples_per_sec": 70000, "training_step_time_ms": 180}) for _ in range(5)]
        result = self.eff.measure(self.job, snaps)
        self.assertFalse(result["acceptable"])


class TestEscalationAgent(unittest.TestCase):
    def setUp(self):
        self.config = AgentConfig()
        self.agent = EscalationAgent(self.config)

    def test_escalate_on_low_efficiency(self):
        from models import Incident

        inc = Incident(node_id="N-1", severity=SeverityLevel.S3)
        inc.efficiency = {"acceptable": False, "efficiency_pct": 70.0}
        inc.validation = {"valid": True}
        result = self.agent.evaluate(inc)
        self.assertTrue(result["escalated"])
        self.assertIn("efficiency_below_threshold", result["reasons"])


if __name__ == "__main__":
    unittest.main()
