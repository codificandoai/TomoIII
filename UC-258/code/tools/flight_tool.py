"""Herramienta simulada de búsqueda de vuelos."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, List

from models import ExternalData
from tools.base import ExternalTool


class FlightSearchTool(ExternalTool):
    """Proveedor de vuelos simulado. Devuelve datos con fuente y confianza."""

    name = "flight_search"

    def __init__(self) -> None:
        self._cache: dict = {}

    def call(self, origin: str, destination: str, date: str, **kwargs: Any) -> ExternalData:
        # Datos verificables simulados; en producción llamaría a Amadeus, Duffel, etc.
        flights = self._search(origin, destination, date)
        return ExternalData(
            value=flights,
            source="simulated_flight_provider",
            confidence=0.85,
            verified=True,
            note="Datos obtenidos de proveedor simulado. Validar con API real en producción.",
        )

    def _search(self, origin: str, destination: str, date: str) -> List[dict]:
        key = (origin.lower(), destination.lower(), date)
        if key not in self._cache:
            base = 120.0
            flights = [
                {
                    "flight_id": "F101",
                    "origin": origin,
                    "destination": destination,
                    "departure": f"{date}T08:00:00",
                    "arrival": f"{date}T10:30:00",
                    "price_usd": base,
                    "seats_left": 5,
                    "class": "economy",
                },
                {
                    "flight_id": "F102",
                    "origin": origin,
                    "destination": destination,
                    "departure": f"{date}T14:00:00",
                    "arrival": f"{date}T16:30:00",
                    "price_usd": base * 1.25,
                    "seats_left": 2,
                    "class": "economy",
                },
                {
                    "flight_id": "F103",
                    "origin": origin,
                    "destination": destination,
                    "departure": f"{date}T18:00:00",
                    "arrival": f"{date}T20:30:00",
                    "price_usd": base * 0.75,
                    "seats_left": 0,
                    "class": "economy",
                },
            ]
            self._cache[key] = flights
        return self._cache[key]
