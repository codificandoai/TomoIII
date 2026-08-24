"""Herramienta simulada de clima."""
from __future__ import annotations

from typing import Any

from models import ExternalData
from tools.base import ExternalTool


class WeatherTool(ExternalTool):
    """Proveedor de clima simulado."""

    name = "weather_forecast"

    def call(self, destination: str, date: str, **kwargs: Any) -> ExternalData:
        return ExternalData(
            value={
                "destination": destination,
                "date": date,
                "condition": "partly_cloudy",
                "temp_c_min": 15,
                "temp_c_max": 22,
                "rain_prob": 0.2,
            },
            source="simulated_weather_api",
            confidence=0.75,
            verified=False,
            note="Pronóstico a 7 días; la confianza disminuye con el horizonte temporal.",
        )
