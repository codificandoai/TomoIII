"""Pruebas unitarias de detección de subutilización de recursos UC-702."""

import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import UnderutilizationThresholds
from models import GPUSnapshot, ResourceSnapshot
from underutilization import evaluate


def _snapshot(**overrides) -> ResourceSnapshot:
    defaults = dict(
        timestamp=datetime.now(timezone.utc),
        cpu_percent=10.0,
        cpu_count_logical=8,
        cpu_count_physical=4,
        load_avg_1m=1.0,
        memory_total_mb=16000.0,
        memory_used_mb=4000.0,
        memory_available_mb=12000.0,
        disk_total_gb=500.0,
        disk_used_gb=100.0,
        disk_free_gb=400.0,
        net_bytes_sent=0,
        net_bytes_recv=0,
        net_sent_rate_bps=0.0,
        net_recv_rate_bps=0.0,
        gpus=[],
    )
    defaults.update(overrides)
    return ResourceSnapshot(**defaults)


class TestUnderutilization(unittest.TestCase):
    def setUp(self):
        self.thresholds = UnderutilizationThresholds()

    def test_idle_node_is_subutilized(self):
        snapshot = _snapshot()
        capacity = evaluate(snapshot, self.thresholds)
        self.assertTrue(capacity.is_subutilized)
        self.assertGreater(capacity.cpu_cores_available, 0)
        self.assertGreater(capacity.memory_available_mb, 0)
        self.assertGreater(capacity.disk_available_gb, 0)

    def test_busy_node_is_not_subutilized(self):
        snapshot = _snapshot(
            cpu_percent=95.0,
            memory_used_mb=15000.0,
            memory_available_mb=1000.0,
            disk_used_gb=490.0,
            disk_free_gb=10.0,
        )
        capacity = evaluate(snapshot, self.thresholds)
        self.assertFalse(capacity.is_subutilized)
        self.assertEqual(capacity.cpu_cores_available, 0.0)
        self.assertEqual(capacity.memory_available_mb, 0.0)
        self.assertEqual(capacity.disk_available_gb, 0.0)

    def test_gpu_idle_counts_as_available(self):
        gpu = GPUSnapshot(
            index=0, name="NVIDIA A100", vendor="nvidia",
            utilization_pct=2.0, memory_total_mb=40000.0, memory_used_mb=1000.0, memory_free_mb=39000.0,
        )
        snapshot = _snapshot(gpus=[gpu])
        capacity = evaluate(snapshot, self.thresholds)
        self.assertEqual(capacity.gpu_count_available, 1)
        self.assertGreater(capacity.gpu_memory_available_mb, 0)

    def test_gpu_busy_excluded(self):
        gpu = GPUSnapshot(
            index=0, name="NVIDIA A100", vendor="nvidia",
            utilization_pct=95.0, memory_total_mb=40000.0, memory_used_mb=39000.0, memory_free_mb=1000.0,
        )
        snapshot = _snapshot(gpus=[gpu])
        capacity = evaluate(snapshot, self.thresholds)
        self.assertEqual(capacity.gpu_count_available, 0)

    def test_gpu_unknown_utilization_is_reported_as_potential(self):
        gpu = GPUSnapshot(index=0, name="Apple M4 Max", vendor="apple")
        snapshot = _snapshot(gpus=[gpu])
        capacity = evaluate(snapshot, self.thresholds)
        self.assertEqual(capacity.gpu_count_available, 1)
        self.assertIn("gpu0_utilization_unknown", capacity.reasons)


if __name__ == "__main__":
    unittest.main()
