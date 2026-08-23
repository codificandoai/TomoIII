"""Pruebas unitarias del recolector de recursos UC-702."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Platform, ResourceSnapshot
from resource_monitor import ResourceMonitor, detect_platform, get_hostname


class TestResourceMonitor(unittest.TestCase):
    def test_detect_platform_returns_known_enum(self):
        self.assertIn(detect_platform(), list(Platform))

    def test_get_hostname_returns_nonempty_string(self):
        self.assertTrue(get_hostname())

    def test_snapshot_has_consistent_fields(self):
        monitor = ResourceMonitor()
        snapshot = monitor.snapshot()
        self.assertGreaterEqual(snapshot.cpu_percent, 0.0)
        self.assertLessEqual(snapshot.cpu_percent, 100.0)
        self.assertGreater(snapshot.cpu_count_logical, 0)
        self.assertGreater(snapshot.memory_total_mb, 0)
        self.assertGreaterEqual(snapshot.memory_available_mb, 0)
        self.assertGreater(snapshot.disk_total_gb, 0)

    def test_snapshot_roundtrip_dict(self):
        monitor = ResourceMonitor()
        snapshot = monitor.snapshot()
        as_dict = snapshot.to_dict()
        rebuilt = ResourceSnapshot.from_dict(as_dict)
        self.assertAlmostEqual(rebuilt.cpu_percent, snapshot.cpu_percent, places=1)
        self.assertEqual(rebuilt.cpu_count_logical, snapshot.cpu_count_logical)
        self.assertEqual(len(rebuilt.gpus), len(snapshot.gpus))

    def test_second_snapshot_computes_net_rate(self):
        monitor = ResourceMonitor()
        monitor.snapshot()
        second = monitor.snapshot()
        self.assertGreaterEqual(second.net_sent_rate_bps, 0.0)
        self.assertGreaterEqual(second.net_recv_rate_bps, 0.0)


if __name__ == "__main__":
    unittest.main()
