"""Motor de planificación multi-opción para UC-265.

Genera planes candidatos diversos usando estrategias (optimista, conservadora,
balanceada, aleatoria) y MCTS completo sobre el espacio de acciones.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config import AppConfig, ModelConfig, get_config
from mcts import MCTSPlanner
from models import PlanAction, TravelPlanRequest, WorldModelState
from travel_world import TravelWorldSimulator
from world_model import TravelWorldModel


class PlanGenerator:
    """Genera planes candidatos a partir del world model y el simulador."""

    def __init__(
        self,
        simulator: TravelWorldSimulator,
        config: ModelConfig,
    ) -> None:
        self.simulator = simulator
        self.config = config

    def generate(
        self,
        request: TravelPlanRequest,
        num_plans: Optional[int] = None,
        world_model: Optional[TravelWorldModel] = None,
        initial_state: Optional[WorldModelState] = None,
    ) -> Tuple[List[List[PlanAction]], Dict[str, Any]]:
        """Devuelve una lista de secuencias de acciones candidatas.

        Si se provee `world_model` e `initial_state`, también ejecuta MCTS para
        generar un plan basado en búsqueda en árbol.
        """
        num_plans = num_plans or self.config.num_candidate_plans
        prefs = request.preferences or {}

        outbound = self.simulator.search_flights(
            request.origin, request.destination, request.departure_date, prefs
        )
        if not outbound:
            return [], {"error": "No outbound flights"}

        return_flights: List[Dict[str, Any]] = []
        if request.return_date:
            return_flights = self.simulator.search_flights(
                request.destination, request.origin, request.return_date, prefs
            )

        hotels: List[Dict[str, Any]] = []
        if request.return_date:
            # llegada = fecha de salida + 1 día como simplificación
            arrival = _add_days(request.departure_date, 1)
            hotels = self.simulator.search_hotels(
                request.destination, arrival, request.return_date
            )

        strategies = ["optimistic", "conservative", "balanced", "random"]
        candidates: List[List[PlanAction]] = []
        rng = np.random.default_rng(hash(request.request_id) % 2**32)

        per_strategy = max(1, num_plans // len(strategies))
        for strategy in strategies:
            for _ in range(per_strategy):
                plan = self._build_plan_for_strategy(
                    strategy, outbound, return_flights, hotels, request, rng
                )
                if plan:
                    candidates.append(plan)

        # Completar hasta num_plans con variaciones aleatorias
        while len(candidates) < num_plans:
            plan = self._build_plan_for_strategy(
                "random", outbound, return_flights, hotels, request, rng
            )
            if plan:
                candidates.append(plan)

        # MCTS completo sobre los niveles de acciones disponibles
        if world_model is not None and initial_state is not None:
            levels = self._action_levels(outbound, hotels, return_flights, request, rng)
            mcts = MCTSPlanner(world_model, self.config.mcts)
            mcts_plan = mcts.search(
                initial_state,
                levels,
                rng=rng,
                request=request.to_state(),
            )
            if mcts_plan:
                candidates.insert(0, mcts_plan)

        return candidates, {"strategies": strategies + ["mcts"], "generated": len(candidates)}

    def _action_levels(
        self,
        outbound: List[Dict[str, Any]],
        hotels: List[Dict[str, Any]],
        return_flights: List[Dict[str, Any]],
        request: TravelPlanRequest,
        rng: np.random.Generator,
    ) -> List[List[PlanAction]]:
        """Construye los niveles de acciones posibles para MCTS."""
        levels: List[List[PlanAction]] = []
        if outbound:
            levels.append([_flight_action(1, f, request.travelers) for f in outbound])
        if hotels:
            levels.append([_hotel_action(2, h, _nights_between(h["check_in"], h["check_out"])) for h in hotels])
        if return_flights:
            levels.append([_flight_action(3, f, request.travelers) for f in return_flights])
        # Submuestrear niveles grandes para MCTS eficiente
        max_options = 6
        sampled_levels = []
        for level in levels:
            if len(level) > max_options:
                idx = rng.choice(len(level), size=max_options, replace=False)
                sampled_levels.append([level[i] for i in idx])
            else:
                sampled_levels.append(level)
        return sampled_levels

    def _build_plan_for_strategy(
        self,
        strategy: str,
        outbound: List[Dict[str, Any]],
        return_flights: List[Dict[str, Any]],
        hotels: List[Dict[str, Any]],
        request: TravelPlanRequest,
        rng: np.random.Generator,
    ) -> List[PlanAction]:
        plan: List[PlanAction] = []
        step = 1

        def pick(options: List[Dict[str, Any]], criterion: str) -> Optional[Dict[str, Any]]:
            if not options:
                return None
            if criterion == "cheapest":
                return min(options, key=lambda x: x.get("price_usd") or x.get("price_per_night_usd", 1e9))
            if criterion == "shortest":
                return min(options, key=lambda x: x.get("duration_minutes", 1e9))
            if criterion == "best_rating":
                return max(options, key=lambda x: x.get("rating", 0))
            if criterion == "direct":
                directs = [o for o in options if o.get("direct")]
                return rng.choice(directs) if directs else rng.choice(options)
            if criterion == "airline_preferred":
                pref = (request.preferences or {}).get("airline")
                matches = [o for o in options if o.get("airline") == pref]
                return rng.choice(matches) if matches else rng.choice(options)
            return rng.choice(options)

        # Outbound
        criterion = {
            "optimistic": "cheapest",
            "conservative": "direct",
            "balanced": "airline_preferred",
            "random": "random",
        }.get(strategy, "random")
        flight_out = pick(outbound, criterion)
        if not flight_out:
            return []
        plan.append(_flight_action(step, flight_out, request.travelers))
        step += 1

        # Hotel
        if hotels:
            hotel_criterion = {
                "optimistic": "cheapest",
                "conservative": "best_rating",
                "balanced": "best_rating",
                "random": "random",
            }.get(strategy, "random")
            hotel = pick(hotels, hotel_criterion)
            if hotel:
                nights = _nights_between(hotel["check_in"], hotel["check_out"])
                plan.append(_hotel_action(step, hotel, nights))
                step += 1

        # Return flight
        if return_flights:
            ret_criterion = {
                "optimistic": "cheapest",
                "conservative": "direct",
                "balanced": "shortest",
                "random": "random",
            }.get(strategy, "random")
            flight_ret = pick(return_flights, ret_criterion)
            if flight_ret:
                plan.append(_flight_action(step, flight_ret, request.travelers))
                step += 1

        return plan


def _flight_action(step: int, flight: Dict[str, Any], travelers: int) -> PlanAction:
    cost = flight.get("price_usd", 0.0) * max(1, travelers)
    return PlanAction(
        step=step,
        action_type="flight",
        item_id=flight["flight_id"],
        item_name=f"{flight['origin']} -> {flight['destination']} ({flight['airline']})",
        details=copy.deepcopy(flight),
        estimated_cost=round(cost, 2),
        estimated_success_prob=0.95,
    )


def _hotel_action(step: int, hotel: Dict[str, Any], nights: int) -> PlanAction:
    cost = hotel.get("price_per_night_usd", 0.0) * nights
    return PlanAction(
        step=step,
        action_type="hotel",
        item_id=hotel["hotel_id"],
        item_name=hotel["name"],
        details=copy.deepcopy(hotel),
        estimated_cost=round(cost, 2),
        estimated_success_prob=0.95,
    )


def _add_days(date_str: str, days: int) -> str:
    dt = datetime.fromisoformat(date_str)
    return (dt + timedelta(days=days)).date().isoformat()


def _nights_between(check_in: str, check_out: str) -> int:
    a = datetime.fromisoformat(check_in).date()
    b = datetime.fromisoformat(check_out).date()
    return max(1, (b - a).days)
