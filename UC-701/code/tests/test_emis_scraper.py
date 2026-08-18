"""Pruebas unitarias del scraper de EMIS para UC-701."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emis_scraper import scrape_kpis, scrape_multi_country, to_analyze_payload


class TestEmisScraper(unittest.TestCase):
    def _mock_response(self, text: str, status: int = 200) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status
        resp.text = text
        resp.raise_for_status = MagicMock()
        return resp

    def test_scrape_kpis_parses_indicators(self):
        html = """
        <html><body>
        <h1>Evolution Technologies Group S A S</h1>
        <div class="d-tr">
            <div class="d-tc w-70">Net sales revenue</div>
            <div class="d-tc w-30 ta-r nobr">-26.71%▼</div>
        </div>
        <div class="d-tr">
            <div class="d-tc w-70">Operating Profit</div>
            <div class="d-tc w-30 ta-r nobr">-90.97%▼</div>
        </div>
        <div class="d-tr">
            <div class="d-tc w-70">Quick Ratio</div>
            <div class="d-tc w-30 ta-r nobr">0.32%▲</div>
        </div>
        </body></html>
        """
        with patch("emis_scraper.requests.Session") as mock_session:
            mock_session.return_value.get.return_value = self._mock_response(html)
            result = scrape_kpis("https://emis.example/profile.html")
        self.assertEqual(result["empresa"], "Evolution Technologies Group S A S")
        self.assertIn("Ingresos netos por ventas", result["indicadores"])
        self.assertIn("Ganancia operativa (EBIT)", result["indicadores"])
        self.assertIn("Prueba Ácida", result["indicadores"])

    def test_to_analyze_payload(self):
        scrape_result = {
            "empresa": "Evo Tech",
            "pais": "CO",
            "url": "...",
            "moneda": "COP",
            "indicadores": {"Ingresos netos por ventas": "-26.71%"},
        }
        payload = to_analyze_payload(scrape_result, fecha_corte="2024-12-31")
        self.assertEqual(payload["empresa"], "Evo Tech")
        self.assertEqual(payload["cortes"][0]["fecha"], "2024-12-31")
        self.assertIn("Ingresos netos por ventas", payload["cortes"][0]["indicadores"])


if __name__ == "__main__":
    unittest.main()
