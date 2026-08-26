"""Simulación determinista de APIs externas (adaptado de UC-261)."""
from __future__ import annotations

import random
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config import get_config
from models import fmt_date, parse_iso


class WorldSimulator:
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

    def inject_event(self, item_id: str, event_type: str, **details: Any) -> None:
        self._events[item_id] = {"event_type": event_type, **details}

    def clear_events(self) -> None:
        self._events.clear()

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
            if origin.lower() == destination.lower():
                return []
            base_price = 120.0 + self._rng.uniform(-20, 80)
            airlines = ["AA", "IB", "LATAM", "AV", "UX", "Delta"]
            aircraft = ["B738", "A320", "B787", "A350", "E190"]
            departures = ["08:00", "11:30", "14:00", "18:00", "20:30"]
            flights = []
            for i, dep in enumerate(departures):
                dep_dt = datetime.fromisoformat(f"{date}T{dep}:00")
                duration = self._rng.choice([90, 120, 150, 180])
                arr_dt = dep_dt + timedelta(minutes=duration)
                direct = duration <= 150
                airline = self._rng.choice(airlines)
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
                    "airline": airline,
                    "flight_number": f"{airline}{100+i}",
                    "aircraft_type": self._rng.choice(aircraft),
                }
                flights.append(flight)
            self._flight_cache[key] = flights
        return list(self._flight_cache[key])

    def book_flight(self, flight_id: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._sleep()
        import uuid as _uuid

        for flights in self._flight_cache.values():
            for f in flights:
                if f["flight_id"] == flight_id:
                    if f["seats_left"] <= 0:
                        return {"status": "FAILED", "error": "flight_sold_out"}
                    f["seats_left"] -= 1
                    return {"status": "BOOKED", "confirmation": f"BK-{flight_id}-{_uuid.uuid4().hex[:6].upper()}"}
        return {"status": "FAILED", "error": "flight_not_found"}

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
        import uuid as _uuid

        for hotels in self._hotel_cache.values():
            for h in hotels:
                if h["hotel_id"] == hotel_id:
                    if h["rooms_left"] <= 0:
                        return {"status": "FAILED", "error": "hotel_sold_out"}
                    h["rooms_left"] -= 1
                    return {"status": "BOOKED", "confirmation": f"HT-{hotel_id}-{_uuid.uuid4().hex[:6].upper()}"}
        return {"status": "FAILED", "error": "hotel_not_found"}

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
