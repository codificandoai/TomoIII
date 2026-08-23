"""Pruebas de integración de la API REST Flask de UC-702."""

import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import app, pool


def _snapshot_payload(**overrides):
    payload = {
        "cpu_percent": 5.0,
        "cpu_count_logical": 8,
        "cpu_count_physical": 4,
        "memory_total_mb": 16000.0,
        "memory_used_mb": 2000.0,
        "memory_available_mb": 14000.0,
        "disk_total_gb": 500.0,
        "disk_used_gb": 50.0,
        "disk_free_gb": 450.0,
        "net_bytes_sent": 100,
        "net_bytes_recv": 200,
        "gpus": [],
    }
    payload.update(overrides)
    return payload


class TestAPIIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def setUp(self):
        self.node_id = f"node-test-{uuid.uuid4().hex[:8]}"

    def tearDown(self):
        pool.remove_node(self.node_id)

    def test_health(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["data"]["service"], "uc702-capacity-pool")

    def test_schema_has_input_and_output_cards(self):
        resp = self.client.get("/api/v1/schema")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()["data"]
        self.assertIn("input_cards", data)
        self.assertIn("output_cards", data)
        self.assertTrue(any("nodes/register" in c["endpoint"] for c in data["input_cards"]))

    def test_register_node_requires_node_id(self):
        resp = self.client.post("/api/v1/nodes/register", json={})
        self.assertEqual(resp.status_code, 400)

    def test_register_and_get_node(self):
        resp = self.client.post(
            "/api/v1/nodes/register",
            json={"node_id": self.node_id, "provider": "on-premise", "site": "campus-a"},
        )
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(f"/api/v1/nodes/{self.node_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["data"]["node_id"], self.node_id)

    def test_get_unknown_node_returns_404(self):
        resp = self.client.get("/api/v1/nodes/does-not-exist")
        self.assertEqual(resp.status_code, 404)

    def test_ingest_telemetry_autoregisters_node(self):
        resp = self.client.post(
            f"/api/v1/nodes/{self.node_id}/telemetry", json=_snapshot_payload()
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()["data"]
        self.assertTrue(data["available_capacity"]["is_subutilized"])

    def test_cluster_summary_reflects_ingested_node(self):
        self.client.post(f"/api/v1/nodes/{self.node_id}/telemetry", json=_snapshot_payload())
        resp = self.client.get("/api/v1/cluster/summary")
        self.assertEqual(resp.status_code, 200)
        summary = resp.get_json()["data"]
        self.assertGreaterEqual(summary["nodes_active"], 1)
        self.assertGreater(summary["capacity_available"]["cpu_cores"], 0)

    def test_allocate_and_release(self):
        self.client.post(f"/api/v1/nodes/{self.node_id}/telemetry", json=_snapshot_payload())
        resp = self.client.post(
            "/api/v1/pool/allocate", json={"requester": "app-test", "cpu_cores": 1.0, "memory_mb": 100.0}
        )
        self.assertEqual(resp.status_code, 200)
        allocation_id = resp.get_json()["data"]["allocation_id"]

        resp = self.client.post("/api/v1/pool/release", json={"allocation_id": allocation_id})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["data"]["released"])

    def test_allocate_without_capacity_returns_409(self):
        self.client.post(
            f"/api/v1/nodes/{self.node_id}/telemetry",
            json=_snapshot_payload(cpu_percent=99.0, memory_available_mb=10.0, disk_free_gb=1.0),
        )
        resp = self.client.post(
            "/api/v1/pool/allocate", json={"requester": "app-test", "cpu_cores": 100.0}
        )
        self.assertEqual(resp.status_code, 409)

    def test_allocate_requires_requester(self):
        resp = self.client.post("/api/v1/pool/allocate", json={"cpu_cores": 1.0})
        self.assertEqual(resp.status_code, 400)

    def test_release_unknown_allocation_returns_404(self):
        resp = self.client.post("/api/v1/pool/release", json={"allocation_id": "missing"})
        self.assertEqual(resp.status_code, 404)

    def test_spot_events_report_and_list(self):
        resp = self.client.post(
            "/api/v1/spot/events",
            json={"node_id": self.node_id, "provider": "aws", "action": "terminate"},
        )
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get("/api/v1/spot/events")
        self.assertEqual(resp.status_code, 200)
        events = resp.get_json()["data"]
        self.assertTrue(any(e["node_id"] == self.node_id for e in events))

    def test_metrics_endpoint(self):
        resp = self.client.get("/api/v1/metrics")
        self.assertEqual(resp.status_code, 200)

    def test_dashboards_endpoint(self):
        resp = self.client.get("/api/v1/dashboards")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()["data"]
        self.assertIn("uc702-cluster-overview", data)

    def test_frontend_served(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"UC-702", resp.data)


if __name__ == "__main__":
    unittest.main()
