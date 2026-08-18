"""Pruebas de integración de la API REST Flask de UC-701."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import app


class TestAPIIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def test_health(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["data"]["service"], "uc701-financial-predictor")

    def test_schema(self):
        resp = self.client.get("/api/v1/schema")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()["data"]
        self.assertIn("input_cards", data)
        self.assertIn("output_cards", data)

    def test_analyze(self):
        payload = {
            "empresa": "Empresa API Test",
            "cortes": [
                {
                    "fecha": "2024-12-31",
                    "indicadores": {
                        "Ingresos netos por ventas": -26.71,
                        "Ganancia operativa (EBIT)": -90.97,
                        "Prueba Ácida": 0.32,
                        "Total de patrimonio": -57.93,
                        "Relación Deuda/Capital": 37.68,
                    },
                }
            ],
        }
        resp = self.client.post("/api/v1/analyze", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()["data"]
        self.assertEqual(data["empresa"], "Empresa API Test")
        self.assertIn("score_riesgo_financiero", data)
        self.assertIn("recomendaciones", data)

    def test_predict(self):
        payload = {
            "empresa": "Empresa Predicción",
            "cortes": [
                {
                    "fecha": "2023-12-31",
                    "indicadores": {
                        "Ingresos netos por ventas": -10.0,
                        "Ganancia operativa (EBIT)": -30.0,
                        "Prueba Ácida": 0.55,
                    },
                },
                {
                    "fecha": "2024-12-31",
                    "indicadores": {
                        "Ingresos netos por ventas": -26.71,
                        "Ganancia operativa (EBIT)": -90.97,
                        "Prueba Ácida": 0.32,
                    },
                },
            ],
        }
        resp = self.client.post("/api/v1/predict", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()["data"]
        self.assertIn("probabilidad_declive_pct", data)
        self.assertIn("escenario_esperado", data)

    def test_dashboards(self):
        resp = self.client.get("/api/v1/dashboards")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()["data"]
        self.assertIn("uc701-financial-risk", [d["name"] for d in data["dashboards"]])

    def test_metrics(self):
        resp = self.client.get("/api/v1/metrics")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("uc701", resp.get_data(as_text=True).lower())


if __name__ == "__main__":
    unittest.main()
