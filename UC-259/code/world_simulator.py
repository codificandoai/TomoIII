"""Simulación determinista de APIs externas: vuelos, hoteles, clima y eventos."""
from __future__ import annotations

import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config import get_config
from models import fmt_date, now_iso, parse_iso


class WorldSimulator:
    """Proveedor externo simulado intercambiable.

    La aleatoriedad está controlada por ``seed`` para garantizar tests
    deterministas. Los eventos (retrasos, cancelaciones, overbooking) se
    pueden inyectar explícitamente vía ``inject_event`` o dejar que surjan
    con ``random_event_prob``.
    """

    def __init__(self, config: Optional[Any] = None) -> None:
        self.config = config or get_config().world
        self._rng = random.Random(self.config.seed)
        self._events: Dict[str, Dict[str, Any]] = {}
        self._latency_s = max(0, self.config.simulated_latency_ms) / 1000.0
        self._flight_cache: Dict[tuple, List[Dict[str, Any]]] = {}
        self._hotel_cache: Dict[tuple, List[Dict[str, Any]]] = {}

    def _sleep(self) -> None:
        if self._latency_s:
            time.sleep(self._latency_s)

    # --------------------------------------------------------------------------
    # Inyección de eventos del mundo real
    # --------------------------------------------------------------------------
    def inject_event(self, item_id: str, event_type: str, **details: Any) -> None:
        """Inyecta un evento para que ``check_status`` lo reporte."""
        self._events[item_id] = {"event_type": event_type, **details}

    def clear_events(self) -> None:
        self._events.clear()

    # --------------------------------------------------------------------------
    # Vuelos
    # --------------------------------------------------------------------------
    def search_flights(
        self,
        origin: str,
        destination: str,
        date: str,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        preferences = preferences or {}
        key = (origin.lower(), destination.lower(), date)
        if key not in self._flight_cache:
            base_price = 120.0 + self._rng.uniform(-20, 80)
            if origin.lower() == destination.lower():
                return []
            departures = ["08:00", "11:30", "14:00", "18:00", "20:30"]
            flights = []
            for i, dep in enumerate(departures):
                dep_dt = datetime.fromisoformat(f"{date}T{dep}:00")
                duration = self._rng.choice([90, 120, 150, 180])
                arr_dt = dep_dt + timedelta(minutes=duration)
                direct = duration <= 150
                flight = {
                    "flight_id": f"FL-{origin[:3].upper()}{destination[:3].upper()}-{100+i}",
                    "origin": origin,
                    "destination": destination,
                    "departure": dep_dt.isoformat(),
                    "arrival": arr_dt.isoformat(),
                    "duration_minutes": duration,
                    "price_usd": round(base_price + self._rng.uniform(0, 60) + (0 if direct else 40), 2),
                    "seats_left": self._rng.randint(1, 20),
                    "cabin_class": "economy",
                    "direct": direct,
                }
                flights.append(flight)
            self._flight_cache[key] = flights
        return list(self._flight_cache[key])

    def book_flight(self, flight_id: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._sleep()
        # Buscar vuelo en caché para validar disponibilidad
        for flights in self._flight_cache.values():
            for f in flights:
                if f["flight_id"] == flight_id:
                    if f["seats_left"] <= 0:
                        return {
                            "status": "FAILED",
                            "error": "flight_sold_out",
                            "message": f"Flight {flight_id} is sold out.",
                        }
                    f["seats_left"] -= 1
                    return {
                        "status": "BOOKED",
                        "confirmation": f"BK-{flight_id}-{uuid.uuid4().hex[:6].upper()}",
                        "flight_id": flight_id,
                    }
        return {
            "status": "FAILED",
            "error": "flight_not_found",
            "message": f"Flight {flight_id} not found.",
        }

    def check_status(self, item_id: str) -> Dict[str, Any]:
        """Consulta el estado real de un ítem reservado."""
        if item_id in self._events:
            event = self._events[item_id]
            return {
                "status": event.get("event_type", "ON_TIME").upper(),
                "item_id": item_id,
                **event,
            }
        # Evento aleatorio según configuración
        if (
            self.config.random_event_prob > 0
            and self._rng.random() < self.config.random_event_prob
        ):
            return {
                "status": "DELAYED",
                "item_id": item_id,
                "delay_minutes": self._rng.choice([60, 120, 180]),
                "reason": "Simulated external disruption",
            }
        return {"status": "ON_TIME", "item_id": item_id}

    def rebook_flight(
        self,
        old_flight_id: str,
        origin: str,
        destination: str,
        date: str,
        after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Busca la mejor alternativa disponible después de un horario dado.

        Si el vuelo más barato está agotado, prueba con los siguientes candidatos
        hasta encontrar uno con asientos disponibles.
        """
        self._sleep()

        def _pick(candidates: list) -> Optional[Dict[str, Any]]:
            candidates = sorted(candidates, key=lambda c: (c["price_usd"], c["departure"]))
            for best in candidates:
                if best["seats_left"] <= 0:
                    continue
                best["seats_left"] -= 1
                return best
            return None

        def _same_day() -> list:
            flights = self.search_flights(origin, destination, date)
            if after:
                after_dt = parse_iso(after)
                flights = [
                    c
                    for c in flights
                    if parse_iso(c["departure"]) and parse_iso(c["departure"]) > after_dt
                ]
            return [c for c in flights if c["flight_id"] != old_flight_id]

        best = _pick(_same_day())
        if best:
            return {
                "status": "REBOOKED",
                "confirmation": f"RB-{best['flight_id']}-{uuid.uuid4().hex[:6].upper()}",
                "flight": best,
            }

        # Fallback: buscar al día siguiente si no hay alternativas el mismo día
        next_date_dt = parse_iso(f"{date}T00:00:00") or datetime.fromisoformat(f"{date}T00:00:00")
        next_date = (next_date_dt.date() + timedelta(days=1)).isoformat()
        best = _pick(
            [
                c
                for c in self.search_flights(origin, destination, next_date)
                if c["flight_id"] != old_flight_id
            ]
        )
        if best:
            return {
                "status": "REBOOKED",
                "confirmation": f"RB-{best['flight_id']}-{uuid.uuid4().hex[:6].upper()}",
                "flight": best,
            }

        return {
            "status": "FAILED",
            "error": "no_alternative",
            "message": "No alternative flights available.",
        }

    # --------------------------------------------------------------------------
    # Hoteles
    # --------------------------------------------------------------------------
    def search_hotels(
        self,
        destination: str,
        check_in: str,
        check_out: str,
    ) -> List[Dict[str, Any]]:
        key = (destination.lower(), check_in, check_out)
        if key not in self._hotel_cache:
            base = 80.0 + self._rng.uniform(-10, 60)
            hotels = [
                {
                    "hotel_id": f"HT-{destination[:3].upper()}-01",
                    "name": f"{destination} Central Hotel",
                    "destination": destination,
                    "check_in": check_in,
                    "check_out": check_out,
                    "price_per_night_usd": round(base, 2),
                    "rating": 4.5,
                    "rooms_left": self._rng.randint(1, 10),
                    "stars": 4,
                },
                {
                    "hotel_id": f"HT-{destination[:3].upper()}-02",
                    "name": f"Budget Stay {destination}",
                    "destination": destination,
                    "check_in": check_in,
                    "check_out": check_out,
                    "price_per_night_usd": round(base * 0.6, 2),
                    "rating": 3.7,
                    "rooms_left": self._rng.randint(3, 20),
                    "stars": 2,
                },
            ]
            self._hotel_cache[key] = hotels
        return list(self._hotel_cache[key])

    def book_hotel(self, hotel_id: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._sleep()
        for hotels in self._hotel_cache.values():
            for h in hotels:
                if h["hotel_id"] == hotel_id:
                    if h["rooms_left"] <= 0:
                        return {
                            "status": "FAILED",
                            "error": "hotel_sold_out",
                            "message": f"Hotel {hotel_id} is sold out.",
                        }
                    h["rooms_left"] -= 1
                    return {
                        "status": "BOOKED",
                        "confirmation": f"HT-{hotel_id}-{uuid.uuid4().hex[:6].upper()}",
                        "hotel_id": hotel_id,
                    }
        return {
            "status": "FAILED",
            "error": "hotel_not_found",
            "message": f"Hotel {hotel_id} not found.",
        }

    # --------------------------------------------------------------------------
    # Clima y utilidades
    # --------------------------------------------------------------------------
    def check_weather(self, destination: str, date: str) -> Dict[str, Any]:
        conditions = ["sunny", "cloudy", "rainy", "stormy"]
        return {
            "destination": destination,
            "date": date,
            "condition": self._rng.choice(conditions),
            "temperature_c": round(self._rng.uniform(10, 32), 1),
            "source": "simulated_weather_provider",
            "confidence": 0.75,
        }
