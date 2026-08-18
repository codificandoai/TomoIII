"""Pruebas unitarias del core de análisis financiero UC-701."""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import (
    analizar_empresa,
    canonizar_indicador,
    calcular_riesgo_indicador,
    estado_score,
    parsear_numero,
)
from forecasting import calcular_probabilidades_declive, escenario_esperado, predecir


class TestNormalizacion(unittest.TestCase):
    def test_canonizar_alias(self):
        self.assertEqual(canonizar_indicador("Prueba Acida"), "Prueba Ácida")
        self.assertEqual(canonizar_indicador("EBIT"), "Ganancia operativa (EBIT)")
        self.assertEqual(canonizar_indicador("ROE"), "Rendimiento Sobre El Patrimonio (ROE)")
        self.assertIsNone(canonizar_indicador("Indicador inventado"))

    def test_parsear_numeros(self):
        self.assertEqual(parsear_numero("-26,71%"), -26.71)
        self.assertEqual(parsear_numero("(10.5)"), -10.5)
        self.assertTrue(np.isnan(parsear_numero("N/D")))
        self.assertEqual(parsear_numero("0,32"), 0.32)


class TestRiesgoIndicador(unittest.TestCase):
    def test_prueba_acida_critica(self):
        riesgo, estado, severidad, _ = calcular_riesgo_indicador("Prueba Ácida", 0.32)
        self.assertGreaterEqual(riesgo, 90)
        self.assertEqual(severidad, "critico")

    def test_ebit_colapso(self):
        riesgo, estado, severidad, _ = calcular_riesgo_indicador("Ganancia operativa (EBIT)", -90.97)
        self.assertEqual(riesgo, 100.0)
        self.assertEqual(severidad, "critico")

    def test_estado_score(self):
        self.assertEqual(estado_score(85)[0], "Riesgo financiero muy alto")
        self.assertEqual(estado_score(10)[1], "verde")


class TestAnalizarEmpresa(unittest.TestCase):
    def test_analisis_basico(self):
        datos = {
            "empresa": "Empresa Test",
            "cortes": [
                {
                    "fecha": "2024-12-31",
                    "indicadores": {
                        "Ingresos netos por ventas": -26.71,
                        "Ganancia operativa (EBIT)": -90.97,
                        "Prueba Ácida": 0.32,
                        "Total de patrimonio": -57.93,
                    },
                }
            ],
        }
        resultado = analizar_empresa(datos)
        self.assertEqual(resultado["empresa"], "Empresa Test")
        self.assertGreaterEqual(resultado["score_riesgo_financiero"], 0)
        self.assertLessEqual(resultado["score_riesgo_financiero"], 100)
        self.assertIn("diagnosticos", resultado)
        self.assertIn("recomendaciones", resultado)


class TestForecasting(unittest.TestCase):
    def test_probabilidades_con_tendencia_negativa(self):
        proyecciones = {
            "Ingresos netos por ventas": {
                "valor_actual": -10.0,
                "proyeccion_1y": -30.0,
                "riesgo_actual": 60.0,
                "riesgo_proyectado": 80.0,
            },
            "Ganancia operativa (EBIT)": {
                "valor_actual": -30.0,
                "proyeccion_1y": -95.0,
                "riesgo_actual": 80.0,
                "riesgo_proyectado": 100.0,
            },
        }
        # Simular estructura con pesos reales
        from forecasting import proyectar_indicadores
        import pandas as pd

        historial = pd.DataFrame([
            {"empresa": "T", "fecha": "2023-12-31", "indicador": "Ingresos netos por ventas", "valor": -10.0, "unidad": "pct"},
            {"empresa": "T", "fecha": "2024-12-31", "indicador": "Ingresos netos por ventas", "valor": -26.71, "unidad": "pct"},
            {"empresa": "T", "fecha": "2023-12-31", "indicador": "Ganancia operativa (EBIT)", "valor": -30.0, "unidad": "pct"},
            {"empresa": "T", "fecha": "2024-12-31", "indicador": "Ganancia operativa (EBIT)", "valor": -90.97, "unidad": "pct"},
        ])
        resultado = predecir(historial, horizonte_anios=1)
        self.assertIn("probabilidad_declive_pct", resultado)
        self.assertIn("escenario_esperado", resultado)
        self.assertGreater(resultado["probabilidad_declive_pct"], resultado["probabilidad_sostenimiento_pct"])

    def test_escenario_esperado(self):
        self.assertIn("Declive", escenario_esperado(80))
        self.assertIn("Sostenimiento", escenario_esperado(20))


if __name__ == "__main__":
    unittest.main()
