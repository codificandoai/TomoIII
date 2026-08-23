"""Pruebas unitarias del pool compartido de capacidad UC-702."""

import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capacity_pool import CapacityPool, InsufficientCapacityError
from config import MonitorConfig
from models import InstanceLifecycle, NodeInfo, Platform, ProviderKind, ResourceDemand, ResourceSnapshot


def _snapshot(**overrides) -> ResourceSnapshot:
    defaults = dict(
        timestamp=datetime.now(timezone.utc),
        cpu_percent=5.0,
        cpu_count_logical=8,
        cpu_count_physical=4,
        load_avg_1m=0.5,
        memory_total_mb=16000.0,
        memory_used_mb=2000.0,
        memory_available_mb=14000.0,
        disk_total_gb=500.0,
        disk_used_gb=50.0,
        disk_free_gb=450.0,
        net_bytes_sent=0,
        net_bytes_recv=0,
        net_sent_rate_bps=0.0,
        net_recv_rate_bps=0.0,
        gpus=[],
    )
    defaults.update(overrides)
    return ResourceSnapshot(**defaults)


def _node_info(node_id: str, site: str = "campus-a") -> NodeInfo:
    return NodeInfo(
        node_id=node_id,
        hostname=node_id,
        platform=Platform.LINUX,
        architecture="x86_64",
        provider=ProviderKind.ON_PREMISE,
        lifecycle=InstanceLifecycle.ON_DEMAND,
        site=site,
    )


class TestCapacityPool(unittest.TestCase):
    def setUp(self):
        self.pool = CapacityPool(config=MonitorConfig())

    def test_register_and_ingest(self):
        self.pool.register_node(_node_info("n1"))
        capacity = self.pool.ingest_snapshot("n1", _snapshot())
        self.assertTrue(capacity.is_subutilized)
        record = self.pool.get_node("n1")
        self.assertIsNotNone(record.last_capacity)

    def test_ingest_unregistered_node_raises(self):
        with self.assertRaises(KeyError):
            self.pool.ingest_snapshot("missing", _snapshot())

    def test_cluster_summary_aggregates_by_site(self):
        self.pool.register_node(_node_info("n1", site="campus-a"))
        self.pool.register_node(_node_info("n2", site="campus-b"))
        self.pool.ingest_snapshot("n1", _snapshot())
        self.pool.ingest_snapshot("n2", _snapshot())
        summary = self.pool.cluster_summary()
        self.assertEqual(summary["nodes_active"], 2)
        self.assertIn("campus-a", summary["by_site"])
        self.assertIn("campus-b", summary["by_site"])

    def test_allocate_picks_node_with_capacity(self):
        self.pool.register_node(_node_info("n1"))
        self.pool.ingest_snapshot("n1", _snapshot())
        allocation = self.pool.allocate(ResourceDemand(requester="app1", cpu_cores=1.0, memory_mb=100.0))
        self.assertEqual(allocation.node_id, "n1")
        node = self.pool.get_node("n1")
        self.assertLess(node.last_capacity.cpu_cores_available, 8 * 0.95 + 1e-6)

    def test_allocate_raises_when_no_capacity(self):
        self.pool.register_node(_node_info("n1"))
        self.pool.ingest_snapshot("n1", _snapshot(cpu_percent=99.0, memory_available_mb=100.0, disk_free_gb=1.0))
        with self.assertRaises(InsufficientCapacityError):
            self.pool.allocate(ResourceDemand(requester="app1", cpu_cores=10.0))

    def test_release_returns_capacity(self):
        self.pool.register_node(_node_info("n1"))
        self.pool.ingest_snapshot("n1", _snapshot())
        allocation = self.pool.allocate(ResourceDemand(requester="app1", cpu_cores=1.0))
        before = self.pool.get_node("n1").last_capacity.cpu_cores_available
        released = self.pool.release(allocation.allocation_id)
        self.assertTrue(released.released)
        after = self.pool.get_node("n1").last_capacity.cpu_cores_available
        self.assertGreater(after, before)

    def test_release_unknown_allocation_raises(self):
        with self.assertRaises(KeyError):
            self.pool.release("does-not-exist")

    def test_preferred_site_is_respected(self):
        self.pool.register_node(_node_info("n1", site="campus-a"))
        self.pool.register_node(_node_info("n2", site="campus-b"))
        self.pool.ingest_snapshot("n1", _snapshot())
        self.pool.ingest_snapshot("n2", _snapshot())
        allocation = self.pool.allocate(
            ResourceDemand(requester="app1", cpu_cores=1.0, preferred_site="campus-b")
        )
        self.assertEqual(allocation.node_id, "n2")


if __name__ == "__main__":
    unittest.main()
