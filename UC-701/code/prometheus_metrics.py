"""UC-701 — Métricas Prometheus para análisis financiero y predicción de declive."""

from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
except ImportError:  # pragma: no cover
    CONTENT_TYPE_LATEST = "text/plain; charset=utf-8"

    def generate_latest(*_args, **_kwargs):
        return b""

    class _Metric:
        def __init__(self, *args, **kwargs):
            pass

        def set(self, *args, **kwargs):
            pass

        def inc(self, *args, **kwargs):
            pass

    class Gauge(_Metric):
        pass

    class Counter(_Metric):
        pass


class UC701Metrics:
    """Registro y exposición de métricas Prometheus para UC-701."""

    def __init__(self, namespace: str = "uc701"):
        self.namespace = namespace
        self.score_riesgo = Gauge(
            f"{namespace}_score_riesgo_financiero",
            "Score de riesgo financiero actual",
            ["empresa"],
        )
        self.score_proyectado = Gauge(
            f"{namespace}_score_proyectado_1y",
            "Score de riesgo proyectado a 1 año",
            ["empresa"],
        )
        self.prob_declive = Gauge(
            f"{namespace}_probabilidad_declive_pct",
            "Probabilidad de declive financiero",
            ["empresa"],
        )
        self.prob_sostenimiento = Gauge(
            f"{namespace}_probabilidad_sostenimiento_pct",
            "Probabilidad de sostenimiento financiero",
            ["empresa"],
        )
        self.cobertura_datos = Gauge(
            f"{namespace}_cobertura_datos_pct",
            "Porcentaje de cobertura de datos",
            ["empresa"],
        )
        self.riesgo_categoria = Gauge(
            f"{namespace}_riesgo_categoria",
            "Riesgo por categoría",
            ["empresa", "categoria"],
        )
        self.indicador_valor = Gauge(
            f"{namespace}_indicador_valor",
            "Valor del indicador financiero",
            ["empresa", "indicador"],
        )
        self.analisis_total = Counter(
            f"{namespace}_analisis_total",
            "Total de análisis ejecutados",
            ["nivel_riesgo"],
        )
        self.escenario_info = Gauge(
            f"{namespace}_escenario_esperado_info",
            "Escenario esperado de proyección",
            ["empresa", "escenario"],
        )

    def record_analysis(self, resultado: Dict[str, Any]) -> None:
        empresa = resultado.get("empresa", "unknown")
        if resultado.get("score_riesgo_financiero") is not None:
            self.score_riesgo.labels(empresa=empresa).set(resultado["score_riesgo_financiero"])
        if resultado.get("cobertura_datos_pct") is not None:
            self.cobertura_datos.labels(empresa=empresa).set(resultado["cobertura_datos_pct"])
        for categoria, riesgo in (resultado.get("riesgo_por_categoria") or {}).items():
            self.riesgo_categoria.labels(empresa=empresa, categoria=categoria).set(riesgo)
        for d in resultado.get("diagnosticos", []):
            if d.get("valor") is not None:
                self.indicador_valor.labels(empresa=empresa, indicador=d["indicador"]).set(d["valor"])
        self.analisis_total.labels(nivel_riesgo=resultado.get("nivel_riesgo", "Sin calificación")).inc()

    def record_prediction(self, prediccion: Dict[str, Any]) -> None:
        empresa = prediccion.get("empresa", "unknown")
        if prediccion.get("score_proyectado_1y") is not None:
            self.score_proyectado.labels(empresa=empresa).set(prediccion["score_proyectado_1y"])
        if prediccion.get("probabilidad_declive_pct") is not None:
            self.prob_declive.labels(empresa=empresa).set(prediccion["probabilidad_declive_pct"])
        if prediccion.get("probabilidad_sostenimiento_pct") is not None:
            self.prob_sostenimiento.labels(empresa=empresa).set(prediccion["probabilidad_sostenimiento_pct"])
        escenario = prediccion.get("escenario_esperado", "desconocido")
        self.escenario_info.labels(empresa=empresa, escenario=escenario).set(1)

    def render(self) -> bytes:
        return generate_latest()
