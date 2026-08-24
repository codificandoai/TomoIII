"""Herramienta simulada de búsqueda de alojamiento."""
from __future__ import annotations

from typing import Any, List

from models import ExternalData
from tools.base import ExternalTool


class HotelSearchTool(ExternalTool):
    """Proveedor de hoteles simulado."""

    name = "hotel_search"

    def __init__(self) -> None:
        self._cache: dict = {}

    def call(self, destination: str, check_in: str, check_out: str, **kwargs: Any) -> ExternalData:
        hotels = self._search(destination, check_in, check_out)
        return ExternalData(
            value=hotels,
            source="simulated_hotel_provider",
            confidence=0.80,
            verified=True,
            note="Datos de proveedor simulado. Validar con Booking/Amadeus en producción.",
        )

    def _search(self, destination: str, check_in: str, check_out: str) -> List[dict]:
        key = (destination.lower(), check_in, check_out)
        if key not in self._cache:
            self._cache[key] = [
                {
                    "hotel_id": "H001",
                    "name": f"{destination} Central Hotel",
                    "destination": destination,
                    "check_in": check_in,
                    "check_out": check_out,
                    "price_per_night_usd": 150.0,
                    "rating": 4.5,
                    "rooms_left": 3,
                },
                {
                    "hotel_id": "H002",
                    "name": f"Budget Stay {destination}",
                    "destination": destination,
                    "check_in": check_in,
                    "check_out": check_out,
                    "price_per_night_usd": 80.0,
                    "rating": 3.8,
                    "rooms_left": 10,
                },
            ]
        return self._cache[key]
