"""Pruebas de integración de la API REST Flask de UC-700."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import app, orchestrator


class TestAPIIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def test_health(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["data"]["service"], "uc700-self-healing")

    def test_schema(self):
        resp = self.client.get("/api/v1/schema")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("input_cards", data["data"])
        self.assertIn("output_cards", data["data"])
        self.assertTrue(any(card["endpoint"].startswith("POST /api/v1/diagnose") for card in data["data"]["input_cards"]))

    def test_list_agents(self):
        resp = self.client.get("/api/v1/agents")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("TelemetryCollector", data["data"]["agents"])

    def test_diagnose_no_failure(self):
        resp = self.client.post(
            "/api/v1/diagnose",
            data=json.dumps({"node_id": "N-R-A-1", "inject_failure": False}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsNone(data["data"]["anomaly_score"])

    def test_diagnose_with_failure(self):
        resp = self.client.post(
            "/api/v1/diagnose",
            data=json.dumps({"node_id": "N-R-A-1", "device_id": "N-R-A-1-gpu-0", "inject_failure": True}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsNotNone(data["data"]["anomaly_score"])
        self.assertIn(data["data"]["severity"], ["S1", "S2", "S3"])

    def test_remediate_with_failure(self):
        resp = self.client.post(
            "/api/v1/remediate",
            data=json.dumps({"node_id": "N-R-A-1", "device_id": "N-R-A-1-gpu-0", "inject_failure": True, "operator_id": "sre-001"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        inc = data["data"]
        self.assertIn(inc["severity"], ["S1", "S2", "S3", "S4"])
        self.assertIn("trace", inc)
        self.assertIsNotNone(inc["diagnosis"])

    def test_simulate(self):
        resp = self.client.post(
            "/api/v1/simulate",
            data=json.dumps({"node_id": "N-R-A-2", "operator_id": "sre-001"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["data"]["scenario"], "gpu_memory_failure")
        self.assertIn("incident", data["data"])

    def test_incidents_list_and_detail(self):
        self.client.post(
            "/api/v1/simulate",
            data=json.dumps({"node_id": "N-R-A-3"}),
            content_type="application/json",
        )
        list_resp = self.client.get("/api/v1/incidents")
        self.assertEqual(list_resp.status_code, 200)
        incidents = list_resp.get_json()["data"]
        self.assertGreater(len(incidents), 0)
        first_id = incidents[0]["id"]
        detail_resp = self.client.get(f"/api/v1/incidents/{first_id}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.get_json()["data"]["id"], first_id)

    def test_dashboards(self):
        resp = self.client.get("/api/v1/dashboards")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(len(data["data"]["dashboards"]), 2)

    def test_metrics(self):
        resp = self.client.get("/api/v1/metrics")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("uc700", resp.get_data(as_text=True).lower())


if __name__ == "__main__":
    unittest.main()
