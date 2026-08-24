"""Entorno de viajes Komerzio.com: dinámico, parcialmente observable, multiobjetivo.

El agente debe consultar herramientas externas simuladas; nunca inventa precios
ni disponibilidad. Mantiene un itinerario en construcción y detecta información
faltante o restricciones violadas.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config import EnvironmentConfig
from environments.base import Environment
from models import (
    AgentAction,
    ClarificationRequest,
    EnvironmentProperties,
    ExternalData,
    Itinerary,
    ItineraryItem,
    Observation,
    StepResult,
    ToolCall,
    TravelRequest,
)
from tools.currency_tool import CurrencyConverterTool
from tools.flight_tool import FlightSearchTool
from tools.hotel_tool import HotelSearchTool
from tools.weather_tool import WeatherTool


class TravelEnvironment(Environment):
    """Entorno de planificación de viajes con datos externos verificables."""

    def __init__(
        self,
        request: Optional[TravelRequest] = None,
        config: Optional[EnvironmentConfig] = None,
    ) -> None:
        self.config = config or EnvironmentConfig()
        self.request = request or TravelRequest(
            origin="Madrid", destination="París", departure_date="2026-07-15"
        )
        self.tools = {
            "flight_search": FlightSearchTool(),
            "hotel_search": HotelSearchTool(),
            "weather_forecast": WeatherTool(),
            "currency_converter": CurrencyConverterTool(),
        }
        self.tool_calls: List[ToolCall] = []
        self.itinerary: Itinerary = Itinerary(request_id=self.request.request_id)
        self._flight_results: List[dict] = []
        self._hotel_results: List[dict] = []
        self._weather: Optional[ExternalData] = None
        self._events: List[str] = []

    @property
    def properties(self) -> EnvironmentProperties:
        return EnvironmentProperties(
            name="komerzio_travel",
            is_dynamic=True,
            is_deterministic=False,
            is_fully_observable=False,
            is_discrete=True,
            is_episodic=False,
            is_multi_agent=False,
        )

    def get_observation(self) -> Observation:
        return Observation(
            data={
                "request": self.request.to_dict(),
                "itinerary": self.itinerary.to_dict(),
                "tool_calls_count": len(self.tool_calls),
                "events": self._events[-5:],
            },
            hidden={
                "true_demand_spike": False,  # factor oculto que afectaría precios
            },
            confidence=0.75,
            source="komerzio_travel_state",
        )

    def is_valid_action(self, action: Any) -> bool:
        if isinstance(action, AgentAction):
            return action.name in self.tools or action.name in (
                "validate_constraints",
                "generate_itinerary",
                "detect_missing_info",
            )
        return str(action) in self.tools or str(action) in (
            "validate_constraints",
            "generate_itinerary",
            "detect_missing_info",
        )

    def step(self, action: Any) -> StepResult:
        if isinstance(action, AgentAction):
            action_name = action.name
            params = action.parameters
        else:
            action_name = str(action)
            params = {}

        start = time.time()
        result, info = self._execute_action(action_name, params)
        latency_ms = (time.time() - start) * 1000
        self.tool_calls.append(
            ToolCall(tool_name=action_name, parameters=params, result=result, latency_ms=latency_ms)
        )

        reward = 1.0 if result and result.verified else 0.5
        if action_name == "generate_itinerary" and self.itinerary.total_cost > 0:
            reward += 2.0
        return StepResult(
            observation=self.get_observation(),
            reward=reward,
            done=action_name == "generate_itinerary",
            info=info,
        )

    def _execute_action(
        self, action_name: str, params: Dict[str, Any]
    ) -> tuple[Optional[ExternalData], Dict[str, Any]]:
        if action_name == "flight_search":
            origin = params.get("origin", self.request.origin)
            destination = params.get("destination", self.request.destination)
            date = params.get("date", self.request.departure_date)
            data = self.tools["flight_search"].call(origin=origin, destination=destination, date=date)
            self._flight_results = data.value or []
            return data, {"flights_found": len(self._flight_results)}

        if action_name == "hotel_search":
            destination = params.get("destination", self.request.destination)
            check_in = params.get("check_in", self.request.departure_date)
            check_out = params.get("check_out", self.request.return_date)
            data = self.tools["hotel_search"].call(
                destination=destination, check_in=check_in, check_out=check_out
            )
            self._hotel_results = data.value or []
            return data, {"hotels_found": len(self._hotel_results)}

        if action_name == "weather_forecast":
            data = self.tools["weather_forecast"].call(
                destination=params.get("destination", self.request.destination),
                date=params.get("date", self.request.departure_date),
            )
            self._weather = data
            return data, {}

        if action_name == "currency_converter":
            data = self.tools["currency_converter"].call(
                amount=params.get("amount", 1.0),
                from_currency=params.get("from_currency", "USD"),
                to_currency=params.get("to_currency", self.request.currency),
            )
            return data, {}

        if action_name == "validate_constraints":
            issues = self._validate_constraints()
            data = ExternalData(
                value={"valid": len(issues) == 0, "issues": issues},
                source="constraint_validator",
                confidence=1.0,
                verified=True,
            )
            return data, {"issues": issues}

        if action_name == "detect_missing_info":
            missing = self._detect_missing_info()
            data = ExternalData(
                value=missing,
                source="requirement_analyzer",
                confidence=1.0,
                verified=True,
            )
            return data, {"missing": missing}

        if action_name == "generate_itinerary":
            self._generate_itinerary()
            return None, {"itinerary_generated": True}

        return None, {"error": "unknown_action"}

    def _detect_missing_info(self) -> List[dict]:
        missing = []
        if not self.request.return_date:
            missing.append(
                {"field": "return_date", "reason": "Se requiere fecha de regreso para reservar hotel"}
            )
        if self.request.budget is None:
            missing.append(
                {"field": "budget", "reason": "Se requiere presupuesto para validar opciones"}
            )
        return missing

    def _validate_constraints(self) -> List[str]:
        issues = []
        if self.request.budget is not None and self.itinerary.total_cost > self.request.budget:
            issues.append(
                f"Presupuesto excedido: {self.itinerary.total_cost:.2f} > {self.request.budget:.2f}"
            )
        if not self.request.return_date:
            issues.append("Falta fecha de regreso")
        return issues

    def _generate_itinerary(self) -> None:
        """Construye itinerario explicable a partir de datos externos verificados."""
        self.itinerary.items = []
        self.itinerary.assumptions = [
            "Los precios provienen del proveedor simulado; deben validarse con la API real antes de reservar.",
            "El tipo de cambio es referencial.",
        ]
        self.itinerary.missing_info = [m["field"] for m in self._detect_missing_info()]

        if self._flight_results:
            # Elegir vuelo con disponibilidad y mejor ratio precio/confort
            available = [f for f in self._flight_results if f["seats_left"] > 0]
            if not available:
                self.itinerary.missing_info.append("No hay vuelos disponibles")
                available = self._flight_results
            chosen = sorted(available, key=lambda x: x["price_usd"])[0]
            self.itinerary.items.append(
                ItineraryItem(
                    item_type="flight",
                    name=f"Vuelo {chosen['flight_id']}",
                    start_time=chosen["departure"],
                    end_time=chosen["arrival"],
                    cost=chosen["price_usd"] * self.request.travelers,
                    currency="USD",
                    source="flight_search",
                    confidence=0.85,
                    notes=[f"{chosen['seats_left']} asientos restantes"],
                )
            )
            self.itinerary.alternatives = [
                f"Vuelo alternativo {f['flight_id']} por USD {f['price_usd']}"
                for f in self._flight_results
                if f["flight_id"] != chosen["flight_id"]
            ]

        nights = 1
        if self.request.return_date:
            d1 = datetime.fromisoformat(self.request.departure_date)
            d2 = datetime.fromisoformat(self.request.return_date)
            nights = max(1, (d2 - d1).days)

        if self._hotel_results:
            chosen = sorted(self._hotel_results, key=lambda x: -x["rating"])[0]
            self.itinerary.items.append(
                ItineraryItem(
                    item_type="hotel",
                    name=chosen["name"],
                    start_time=self.request.departure_date,
                    end_time=self.request.return_date or self.request.departure_date,
                    cost=chosen["price_per_night_usd"] * nights,
                    currency="USD",
                    source="hotel_search",
                    confidence=0.80,
                    notes=[f"Valoración {chosen['rating']}/5"],
                )
            )

        total = sum(i.cost for i in self.itinerary.items)
        if self.request.currency != "USD":
            conv = self.tools["currency_converter"].call(
                amount=total, from_currency="USD", to_currency=self.request.currency
            )
            self.itinerary.total_cost = conv.value or total
            self.itinerary.currency = self.request.currency
        else:
            self.itinerary.total_cost = total
            self.itinerary.currency = "USD"

        confidences = [i.confidence for i in self.itinerary.items]
        self.itinerary.confidence = sum(confidences) / len(confidences) if confidences else 0.0

    def reset(self) -> Observation:
        self.__init__(self.request, self.config)
        return self.get_observation()

    def get_state(self) -> Dict[str, Any]:
        return self.get_observation().data
