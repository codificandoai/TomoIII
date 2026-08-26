"""Planificación proactiva con políticas evolutivas para UC-262."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from config import get_config
from models import TravelRequest, fmt_date, parse_iso
from world_simulator import WorldSimulator


def default_weights() -> Dict[str, float]:
    return {
        "cost": 0.25,
        "time": 0.20,
        "comfort": 0.15,
        "loyalty": 0.15,
        "risk": 0.25,
    }


def score_flight(flight: Dict[str, Any], request: TravelRequest, genome: Dict[str, Any]) -> float:
    weights = genome.get("weights", default_weights())
    prefs = request.preferences or {}
    profile_prefs = prefs

    # Normalizar precio (menor mejor, asumiendo 300 USD máximo)
    price = flight.get("price_usd", 200.0)
    cost_score = max(0.0, 1.0 - price / 300.0)

    # Tiempo: menor duración mejor
    duration = flight.get("duration_minutes", 120)
    time_score = max(0.0, 1.0 - duration / 300.0)

    # Confort: directo y mejor aerolínea según preferencias
    comfort_score = 0.5
    if flight.get("direct"):
        comfort_score += 0.3
    if flight.get("airline") == profile_prefs.get("airline"):
        comfort_score += 0.2

    # Lealtad: si la aerolínea preferida está presente
    loyalty_score = 1.0 if flight.get("airline") == profile_prefs.get("airline") else 0.0

    # Riesgo: vuelos directos y con buen margen de conexión reducen riesgo
    risk_score = 0.5
    if flight.get("direct"):
        risk_score += 0.3
    # Penalizar aerolíneas con baja confiabilidad (placeholder)
    if flight.get("airline") in ("AV", "UX"):
        risk_score -= 0.1

    total = (
        weights.get("cost", 0.0) * cost_score
        + weights.get("time", 0.0) * time_score
        + weights.get("comfort", 0.0) * comfort_score
        + weights.get("loyalty", 0.0) * loyalty_score
        + weights.get("risk", 0.0) * risk_score
    )
    return round(max(0.0, min(1.0, total)), 4)


def score_hotel(hotel: Dict[str, Any], request: TravelRequest, genome: Dict[str, Any]) -> float:
    weights = genome.get("weights", default_weights())
    prefs = request.preferences or {}
    price = hotel.get("price_per_night_usd", 100.0)
    cost_score = max(0.0, 1.0 - price / 200.0)
    comfort_score = min(1.0, hotel.get("rating", 3.0) / 5.0)
    chain_match = 1.0 if prefs.get("hotel_chain") and prefs.get("hotel_chain") in hotel.get("name", "") else 0.0
    total = (
        weights.get("cost", 0.0) * cost_score
        + weights.get("comfort", 0.0) * comfort_score
        + weights.get("loyalty", 0.0) * chain_match
    )
    return round(max(0.0, min(1.0, total)), 4)


def _make_plan_item(
    step: int,
    item_type: str,
    item_id: str,
    action: str,
    details: Dict[str, Any],
    cost: float,
    currency: str,
    start_time: str,
    end_time: str,
    source: str,
    confidence: float,
    notes: Optional[List[str]] = None,
    dependencies: Optional[List[int]] = None,
) -> Dict[str, Any]:
    return {
        "step": step,
        "item_type": item_type,
        "id": item_id,
        "status": "PENDING",
        "action": action,
        "details": details,
        "cost": round(cost, 2),
        "currency": currency,
        "start_time": start_time,
        "end_time": end_time,
        "source": source,
        "confidence": round(confidence, 4),
        "confirmation": None,
        "notes": notes or [],
        "dependencies": dependencies or [],
    }


def _nights_between(check_in: str, check_out: str) -> int:
    a = parse_iso(check_in) or datetime.fromisoformat(check_in)
    b = parse_iso(check_out) or datetime.fromisoformat(check_out)
    return max(1, (b.date() - a.date()).days)


def _rule_violations(flight: Dict[str, Any], memory_rules: List[str]) -> List[str]:
    violations = []
    for rule in memory_rules:
        if "escala" in rule.lower() and "menores a 90" in rule:
            if not flight.get("direct") and flight.get("duration_minutes", 120) < 90:
                violations.append(rule)
    return violations


def build_plan(
    request: TravelRequest,
    world: WorldSimulator,
    genome: Dict[str, Any],
    memory_rules: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    """Construye un itinerario usando los pesos del genoma y las reglas de memoria."""
    prefs = request.preferences or {}
    memory_rules = memory_rules or []
    itinerary: List[Dict[str, Any]] = []
    reasoning: List[str] = []
    missing_info: List[str] = []

    outbound_flights = world.search_flights(request.origin, request.destination, request.departure_date, prefs)
    if not outbound_flights:
        missing_info.append(f"No flights found {request.origin}->{request.destination} on {request.departure_date}")
        return [], reasoning, missing_info

    scored = [(f, score_flight(f, request, genome)) for f in outbound_flights]
    # Filtrar violaciones duras de reglas de memoria
    filtered = []
    for f, s in scored:
        v = _rule_violations(f, memory_rules)
        if v:
            reasoning.append(f"Excluded {f['flight_id']} due to memory rule: {v[0]}")
            continue
        filtered.append((f, s))
    if not filtered:
        filtered = scored  # fallback si todas violan
    chosen_outbound = max(filtered, key=lambda x: x[1])[0]
    reasoning.append(
        f"Selected outbound {chosen_outbound['flight_id']} (airline={chosen_outbound['airline']}, "
        f"score={score_flight(chosen_outbound, request, genome)}) using genome weights."
    )

    itinerary.append(_make_plan_item(
        step=1,
        item_type="flight",
        item_id=chosen_outbound["flight_id"],
        action=f"Outbound flight {chosen_outbound['flight_id']} {request.origin}->{request.destination}",
        details=chosen_outbound,
        cost=chosen_outbound["price_usd"] * max(1, request.travelers),
        currency=request.currency,
        start_time=chosen_outbound["departure"],
        end_time=chosen_outbound["arrival"],
        source="evolved_policy",
        confidence=0.8,
        notes=[f"Direct={chosen_outbound.get('direct')}", f"Airline={chosen_outbound.get('airline')}"],
    ))

    arrival_date = fmt_date(parse_iso(chosen_outbound["arrival"])) if chosen_outbound else request.departure_date

    if request.return_date:
        hotels = world.search_hotels(request.destination, arrival_date, request.return_date)
        if hotels:
            scored_hotels = [(h, score_hotel(h, request, genome)) for h in hotels]
            chosen_hotel = max(scored_hotels, key=lambda x: x[1])[0]
            nights = _nights_between(arrival_date, request.return_date)
            itinerary.append(_make_plan_item(
                step=2,
                item_type="hotel",
                item_id=chosen_hotel["hotel_id"],
                action=f"Hotel stay at {chosen_hotel['name']} for {nights} nights",
                details=chosen_hotel,
                cost=chosen_hotel["price_per_night_usd"] * nights,
                currency=request.currency,
                start_time=f"{arrival_date}T15:00:00",
                end_time=f"{request.return_date}T11:00:00",
                source="evolved_policy",
                confidence=0.75,
                notes=[f"{nights} nights", f"Rating {chosen_hotel['rating']}"],
                dependencies=[itinerary[-1]["step"]],
            ))
            reasoning.append(f"Selected hotel {chosen_hotel['hotel_id']} based on comfort/cost weights.")
        else:
            missing_info.append(f"No hotels in {request.destination}")

        return_flights = world.search_flights(request.destination, request.origin, request.return_date, prefs)
        if return_flights:
            scored_ret = [(f, score_flight(f, request, genome)) for f in return_flights]
            chosen_return = max(scored_ret, key=lambda x: x[1])[0]
            itinerary.append(_make_plan_item(
                step=3,
                item_type="flight",
                item_id=chosen_return["flight_id"],
                action=f"Return flight {chosen_return['flight_id']} {request.destination}->{request.origin}",
                details=chosen_return,
                cost=chosen_return["price_usd"] * max(1, request.travelers),
                currency=request.currency,
                start_time=chosen_return["departure"],
                end_time=chosen_return["arrival"],
                source="evolved_policy",
                confidence=0.8,
                notes=[f"Direct={chosen_return.get('direct')}", f"Airline={chosen_return.get('airline')}"],
                dependencies=[itinerary[-1]["step"]] if len(itinerary) >= 2 else [itinerary[0]["step"]],
            ))
            reasoning.append(f"Selected return {chosen_return['flight_id']} using evolved policy.")
        else:
            missing_info.append(f"No return flights {request.destination}->{request.origin}")

    if request.budget is not None:
        total = sum(i["cost"] for i in itinerary)
        if total > request.budget:
            missing_info.append(
                f"Estimated cost {total:.2f} {request.currency} exceeds budget {request.budget:.2f}"
            )

    return itinerary, reasoning, missing_info
