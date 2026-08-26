"""Planificación proactiva del itinerario para UC-259."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from models import FlightPlanRequest, fmt_date, parse_iso
from world_simulator import WorldSimulator


def _choose_flight(
    flights: List[Dict[str, Any]],
    preferences: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not flights:
        return None
    optimize = preferences.get("optimize_for", "cheapest")
    if optimize == "fastest":
        flights = sorted(flights, key=lambda f: (f["duration_minutes"], f["price_usd"]))
    elif optimize == "direct":
        direct = [f for f in flights if f.get("direct")]
        flights = sorted(direct or flights, key=lambda f: (not f.get("direct"), f["price_usd"]))
    else:  # cheapest
        flights = sorted(flights, key=lambda f: (f["price_usd"], f["departure"]))
    if preferences.get("direct_flight"):
        direct = [f for f in flights if f.get("direct")]
        if direct:
            flights = direct
    return flights[0]


def _choose_hotel(
    hotels: List[Dict[str, Any]],
    preferences: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not hotels:
        return None
    target_stars = preferences.get("hotel_stars")
    if target_stars:
        matches = [h for h in hotels if h.get("stars") and h["stars"] >= target_stars]
        if matches:
            hotels = matches
    return min(hotels, key=lambda h: h["price_per_night_usd"])


def _nights_between(check_in: str, check_out: str) -> int:
    a = parse_iso(check_in) or datetime.fromisoformat(check_in)
    b = parse_iso(check_out) or datetime.fromisoformat(check_out)
    delta = b.date() - a.date()
    return max(1, delta.days)


def _next_day(date_str: str) -> str:
    dt = parse_iso(date_str) or datetime.fromisoformat(date_str)
    return (dt.date() + timedelta(days=1)).isoformat()


def build_itinerary(
    request: FlightPlanRequest,
    world: WorldSimulator,
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    """Construye un itinerario inicial con vuelo(s), hotel y reuniones.

    Devuelve: (itinerary, assumptions, missing_info).
    """
    prefs = request.preferences or {}
    itinerary: List[Dict[str, Any]] = []
    assumptions: List[str] = []
    missing_info: List[str] = []

    # Vuelo de ida
    outbound_flights = world.search_flights(
        request.origin,
        request.destination,
        request.departure_date,
        prefs,
    )
    chosen_outbound = _choose_flight(outbound_flights, prefs)
    if not chosen_outbound:
        missing_info.append(f"No flights found from {request.origin} to {request.destination} on {request.departure_date}.")
    else:
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
            source="flight_search",
            confidence=0.85,
            notes=[f"Direct={chosen_outbound.get('direct')}", f"Seat preference: {prefs.get('seat', 'any')}"],
        ))
        assumptions.append(
            f"Outbound price {chosen_outbound['price_usd']} USD per traveler x {request.travelers}"
        )

    # Hotel si hay fecha de regreso o se solicita explicitamente
    arrival_date = fmt_date(parse_iso(chosen_outbound["arrival"])) if chosen_outbound else request.departure_date
    hotel_required = request.return_date is not None or prefs.get("hotel_required", True)
    if hotel_required and request.return_date:
        check_in = arrival_date
        check_out = request.return_date
        hotels = world.search_hotels(request.destination, check_in, check_out)
        chosen_hotel = _choose_hotel(hotels, prefs)
        if not chosen_hotel:
            missing_info.append(f"No hotels found in {request.destination} from {check_in} to {check_out}.")
        else:
            nights = _nights_between(check_in, check_out)
            cost = chosen_hotel["price_per_night_usd"] * nights
            itinerary.append(_make_plan_item(
                step=2,
                item_type="hotel",
                item_id=chosen_hotel["hotel_id"],
                action=f"Hotel stay at {chosen_hotel['name']} for {nights} nights",
                details=chosen_hotel,
                cost=cost,
                currency=request.currency,
                start_time=f"{check_in}T15:00:00",
                end_time=f"{check_out}T11:00:00",
                source="hotel_search",
                confidence=0.80,
                notes=[f"{nights} nights", f"Rating {chosen_hotel['rating']}"],
                dependencies=[itinerary[-1]["step"]] if itinerary else [],
            ))
            assumptions.append(f"Hotel rate {chosen_hotel['price_per_night_usd']} USD per night x {nights}")
    elif hotel_required and not request.return_date:
        missing_info.append("Return date is required to book a hotel.")

    # Vuelo de regreso
    if request.return_date and chosen_outbound:
        return_flights = world.search_flights(
            request.destination,
            request.origin,
            request.return_date,
            prefs,
        )
        chosen_return = _choose_flight(return_flights, prefs)
        if not chosen_return:
            missing_info.append(f"No return flights from {request.destination} to {request.origin} on {request.return_date}.")
        else:
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
                source="flight_search",
                confidence=0.85,
                notes=[f"Direct={chosen_return.get('direct')}"],
                dependencies=[itinerary[-1]["step"]] if len(itinerary) >= 2 else [itinerary[0]["step"]],
            ))
            assumptions.append(
                f"Return price {chosen_return['price_usd']} USD per traveler x {request.travelers}"
            )

    # Reunión / actividad opcional
    meeting_time = prefs.get("meeting_time")
    if meeting_time and chosen_outbound:
        meeting_dt = datetime.fromisoformat(f"{arrival_date}T{meeting_time}:00")
        arrival_dt = parse_iso(chosen_outbound["arrival"]) or datetime.fromisoformat(chosen_outbound["arrival"])
        buffer_minutes = int(prefs.get("meeting_buffer_minutes", 120))
        if (meeting_dt - arrival_dt).total_seconds() < buffer_minutes * 60:
            meeting_dt = arrival_dt + timedelta(minutes=buffer_minutes)
            assumptions.append(f"Meeting moved to {meeting_dt.isoformat()} to allow {buffer_minutes}m buffer after arrival.")
        itinerary.append(_make_plan_item(
            step=4,
            item_type="meeting",
            item_id="MEETING-01",
            action=f"Meeting scheduled at {meeting_dt.strftime('%H:%M')}",
            details={"time": meeting_dt.strftime("%H:%M"), "buffer_minutes": buffer_minutes},
            cost=0.0,
            currency=request.currency,
            start_time=meeting_dt.isoformat(),
            end_time=(meeting_dt + timedelta(minutes=60)).isoformat(),
            source="user_preference",
            confidence=0.95,
            notes=["Dependent on flight arrival"],
            dependencies=[itinerary[0]["step"]] if itinerary else [],
        ))

    # Validación presupuesto
    if request.budget is not None:
        estimated_cost = sum(item["cost"] for item in itinerary)
        if estimated_cost > request.budget:
            missing_info.append(
                f"Estimated cost {estimated_cost:.2f} {request.currency} exceeds budget {request.budget:.2f} {request.currency}."
            )

    # Ordenar por step
    itinerary.sort(key=lambda x: x["step"])
    return itinerary, assumptions, missing_info


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
