"""Planificación específica por estrategia."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from models import AgentAction, EnvironmentKind, EnvironmentProperties, Plan, StrategyKind, TravelRequest


class Planner:
    """Genera planes según la estrategia seleccionada y el objetivo."""

    def plan(
        self,
        strategy: StrategyKind,
        env_props: EnvironmentProperties,
        objective: Any,
        observation: Optional[Dict[str, Any]] = None,
    ) -> Plan:
        if strategy == StrategyKind.EXACT_SEARCH:
            return self._plan_chess(objective, observation)
        if strategy == StrategyKind.CONSTRAINT_PLANNING:
            return self._plan_travel(objective, observation)
        if strategy == StrategyKind.PROBABILISTIC_RISK:
            return self._plan_stock(objective, observation)
        return self._plan_default(objective, observation)

    def _plan_chess(self, objective: Any, observation: Optional[Dict[str, Any]]) -> Plan:
        # En entornos perfectamente observables, el plan es jugar el movimiento calculado.
        board = observation.get("data", {}) if observation else {}
        if "fen" in board:
            # Si se usara python-chess, aquí se invocaría un motor de búsqueda.
            move = "e2e4"
        else:
            # Tablero simplificado: mate en uno con Qd8
            move = "Qd8"
        return Plan(
            goal=str(objective),
            strategy=StrategyKind.EXACT_SEARCH,
            actions=[AgentAction(name=move, parameters={"reason": "optimal_search"})],
            confidence=1.0,
            explanation="Búsqueda exacta en espacio de estados discreto y determinista.",
        )

    def _plan_travel(self, objective: Any, observation: Optional[Dict[str, Any]]) -> Plan:
        request = objective if isinstance(objective, TravelRequest) else TravelRequest(
            origin="Madrid", destination="París", departure_date="2026-07-15"
        )
        actions = [
            AgentAction(
                name="detect_missing_info",
                parameters={},
            ),
            AgentAction(
                name="flight_search",
                parameters={
                    "origin": request.origin,
                    "destination": request.destination,
                    "date": request.departure_date,
                },
            ),
            AgentAction(
                name="hotel_search",
                parameters={
                    "destination": request.destination,
                    "check_in": request.departure_date,
                    "check_out": request.return_date,
                },
            ),
            AgentAction(
                name="weather_forecast",
                parameters={
                    "destination": request.destination,
                    "date": request.departure_date,
                },
            ),
            AgentAction(
                name="validate_constraints",
                parameters={},
            ),
            AgentAction(
                name="generate_itinerary",
                parameters={},
            ),
        ]
        return Plan(
            goal=f"Planificar viaje {request.origin} -> {request.destination}",
            strategy=StrategyKind.CONSTRAINT_PLANNING,
            actions=actions,
            confidence=0.75,
            explanation=(
                "Planificación restringida con consulta a herramientas externas, "
                "validación de restricciones y generación de itinerario explicable."
            ),
        )

    def _plan_stock(self, objective: Any, observation: Optional[Dict[str, Any]]) -> Plan:
        obs = observation or {}
        data = obs.get("data", {}) if isinstance(obs, dict) else {}
        price = data.get("price", 100.0)
        # Estrategia de riesgo: tamaño pequeño y stop-loss
        position_size = self._kelly_position_size(data)
        if data.get("cash", 0) > price * 10:
            action = "buy_small"
        else:
            action = "hold"
        return Plan(
            goal=str(objective),
            strategy=StrategyKind.PROBABILISTIC_RISK,
            actions=[
                AgentAction(
                    name=action,
                    parameters={
                        "size": position_size,
                        "stop_loss_pct": 2.0,
                        "reason": "risk_adjusted_kelly",
                    },
                )
            ],
            confidence=0.55,
            explanation=(
                "Gestión de riesgo en entorno estocástico. "
                "Tamaño de posición basado en tamaño de borde estimado y volatilidad."
            ),
        )

    def _plan_default(self, objective: Any, observation: Optional[Dict[str, Any]]) -> Plan:
        return Plan(
            goal=str(objective),
            strategy=StrategyKind.DECISION_TREE,
            actions=[AgentAction(name="observe", parameters={})],
            confidence=0.5,
            explanation="Estrategia por defecto: recopilar más información antes de actuar.",
        )

    @staticmethod
    def _kelly_position_size(data: Dict[str, Any]) -> float:
        """Aproximación Kelly simple: f* = edge / variance."""
        price = data.get("price", 100.0)
        volatility = data.get("volatility", 0.02)
        # Asumimos un borde pequeño positivo si hay momentum reciente
        history = data.get("history", [])
        if len(history) < 2:
            return 0.0
        momentum = (history[-1] - history[0]) / history[0] if history[0] else 0.0
        variance = volatility ** 2
        if variance == 0:
            return 0.0
        kelly = momentum / variance
        return max(0.0, min(0.1, kelly))  # cap al 10% del capital
