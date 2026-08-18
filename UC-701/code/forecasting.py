"""UC-701 — Modelo de predicción de declive financiero y sostenimiento a futuro.

Este módulo proyecta cada indicador disponible usando regresión lineal sobre la
tendencia histórica y combina las proyecciones con el scoring rule-based para
estimar:
  - probabilidad de declive financiero (empeoramiento)
  - probabilidad de sostenimiento / mejora
  - score proyectado a 1 y 2 años
  - escenario más probable
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from core import INDICADORES, analizar_historial_empresa, calcular_riesgo_indicador, estado_score


def _dias_hasta_fecha(fechas: pd.Series) -> np.ndarray:
    """Convierte fechas a días desde la primera observación."""
    base = fechas.min()
    return (fechas - base).dt.days.values.reshape(-1, 1)


def _proyectar_serie(serie: pd.DataFrame, horizonte_dias: int = 365) -> Optional[Dict[str, Any]]:
    """Proyecta un indicador mediante regresión lineal simple."""
    datos = serie.dropna(subset=["valor", "fecha"]).copy()
    if len(datos) < 2:
        return None

    fechas = datos["fecha"]
    y = datos["valor"].values
    X = _dias_hasta_fecha(fechas)

    modelo = LinearRegression()
    modelo.fit(X, y)

    ultima_fecha = fechas.max()
    ultimo_dia = X[-1][0]
    dias_futuros = ultimo_dia + horizonte_dias
    X_futuro = np.array([[dias_futuros]])
    proyeccion = float(modelo.predict(X_futuro)[0])
    pendiente = float(modelo.coef_[0])

    return {
        "valor_actual": float(y[-1]),
        "proyeccion_1y": proyeccion,
        "pendiente_diaria": pendiente,
        "r2": float(modelo.score(X, y)) if len(y) >= 2 else None,
        "ultima_fecha": ultima_fecha.strftime("%Y-%m-%d") if pd.notna(ultima_fecha) else None,
    }


def proyectar_indicadores(historial: pd.DataFrame, horizonte_dias: int = 365) -> Dict[str, Any]:
    """Proyecta todos los indicadores con al menos 2 cortes."""
    historial = historial.copy()
    historial["fecha"] = pd.to_datetime(historial["fecha"], errors="coerce")
    proyecciones = {}
    for indicador in INDICADORES:
        serie = historial[historial["indicador"] == indicador]
        p = _proyectar_serie(serie, horizonte_dias=horizonte_dias)
        if p:
            proyecciones[indicador] = p
    return proyecciones


def _riesgo_proyectado(indicador: str, valor_proyectado: float) -> float:
    riesgo, _, _, _ = calcular_riesgo_indicador(indicador, valor_proyectado)
    return riesgo


def calcular_probabilidades_declive(
    score_actual: float,
    proyecciones: Dict[str, Any],
) -> Dict[str, float]:
    """Calcula probabilidades de declive y sostenimiento a partir del score y proyecciones."""
    if not proyecciones:
        return {
            "probabilidad_declive_pct": 50.0,
            "probabilidad_sostenimiento_pct": 50.0,
            "razonamiento": "Sin historial suficiente para proyección; se asigna distribución neutra.",
        }

    pesos = {ind: INDICADORES[ind]["peso"] for ind in proyecciones}
    total_peso = sum(pesos.values())

    deltas_riesgo = []
    for indicador, p in proyecciones.items():
        riesgo_actual = _riesgo_proyectado(indicador, p["valor_actual"])
        riesgo_futuro = _riesgo_proyectado(indicador, p["proyeccion_1y"])
        delta = riesgo_futuro - riesgo_actual
        deltas_riesgo.append((delta, pesos[indicador]))

    if total_peso == 0:
        delta_ponderado = 0.0
    else:
        delta_ponderado = sum(d * w for d, w in deltas_riesgo) / total_peso

    score_proyectado = max(0.0, min(100.0, score_actual + delta_ponderado))

    # Probabilidad de declive aumenta con score proyectado y con deltas negativos
    probabilidad_declive = min(95.0, max(5.0, score_proyectado * 0.9 + delta_ponderado * 0.5))
    probabilidad_sostenimiento = 100.0 - probabilidad_declive

    return {
        "probabilidad_declive_pct": round(probabilidad_declive, 2),
        "probabilidad_sostenimiento_pct": round(probabilidad_sostenimiento, 2),
        "score_proyectado_1y": round(score_proyectado, 2),
        "delta_score_ponderado": round(delta_ponderado, 2),
        "razonamiento": (
            "El score proyectado a 1 año y la dirección ponderada de los indicadores "
            "disponibles determinan la probabilidad de declive o sostenimiento."
        ),
    }


def escenario_esperado(prob_declive: float) -> str:
    if prob_declive >= 70:
        return "Declive financiero probable"
    if prob_declive >= 50:
        return "Riesgo de deterioro moderado"
    if prob_declive >= 30:
        return "Sostenimiento incierto"
    return "Sostenimiento o mejora probable"


def predecir(historial: pd.DataFrame, horizonte_anios: int = 1) -> Dict[str, Any]:
    """Genera predicción completa de declive/sostenimiento financiero."""
    proyecciones = proyectar_indicadores(historial, horizonte_dias=horizonte_anios * 365)

    # Reutiliza el análisis actual
    resultado = analizar_historial_empresa(historial)
    score_actual = resultado.get("score_riesgo_financiero") or 50.0

    probs = calcular_probabilidades_declive(score_actual, proyecciones)

    indicadores_en_declive = [
        {
            "indicador": ind,
            "valor_actual": p["valor_actual"],
            "proyeccion_1y": p["proyeccion_1y"],
            "riesgo_actual": _riesgo_proyectado(ind, p["valor_actual"]),
            "riesgo_proyectado": _riesgo_proyectado(ind, p["proyeccion_1y"]),
        }
        for ind, p in proyecciones.items()
    ]

    return {
        "empresa": resultado.get("empresa"),
        "fecha_analisis": resultado.get("fecha_analisis"),
        "score_riesgo_actual": score_actual,
        "score_proyectado_1y": probs.get("score_proyectado_1y"),
        "probabilidad_declive_pct": probs["probabilidad_declive_pct"],
        "probabilidad_sostenimiento_pct": probs["probabilidad_sostenimiento_pct"],
        "escenario_esperado": escenario_esperado(probs["probabilidad_declive_pct"]),
        "nivel_riesgo_proyectado": estado_score(probs.get("score_proyectado_1y", score_actual))[0],
        "proyecciones_por_indicador": proyecciones,
        "indicadores_en_declive": indicadores_en_declive,
        "metadata": {
            "modelo": "regresion_lineal_simple_por_indicador",
            "horizonte_anios": horizonte_anios,
            "advertencia": "Proyección basada en tendencia histórica; no incorpora shocks macro, sectoriales ni decisiones gerenciales.",
        },
    }
