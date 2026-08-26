"""Nodos BDI base del grafo LangGraph para UC-261 (adaptados de UC-260)."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config import AgentConfig, get_config
from external_api import FlightDelayPredictor
from models import (
    Belief,
    Desire,
    Experience,
    FlightPlanRequest,
    Intention,
    fmt_date,
    now_iso,
    parse_iso,
)
from planner import build_itinerary
from safety import SafetyGuard
from state import AdaptiveState
from world_simulator import WorldSimulator


class BDINodes:
    """Nodos BDI para planificación base y autocorrección por retrasos."""

    def __init__(
        self,
        world: WorldSimulator,
        predictor: FlightDelayPredictor,
        config: AgentConfig,
        safety: SafetyGuard,
    ) -> None:
        self.world = world
        self.predictor = predictor
        self.config = config
        self.safety = safety

    def _log(self, node: str, message: str, item_id: str = "") -> Dict[str, Any]:
        return {"node": node, "item_id": item_id, "message": message, "timestamp": now_iso()}

    def _itinerary_copy(self, state: AdaptiveState) -> List[Dict[str, Any]]:
        return copy.deepcopy(state["itinerary"])

    def _desires_copy(self, state: AdaptiveState) -> List[Dict[str, Any]]:
        return copy.deepcopy(state.get("desires", []))

    def _intentions_copy(self, state: AdaptiveState) -> List[Dict[str, Any]]:
        return copy.deepcopy(state.get("intentions", []))

    def _find_item(self, itinerary: List[Dict[str, Any]], item_id: str) -> Optional[Dict[str, Any]]:
        for item in itinerary:
            if item["id"] == item_id:
                return item
        return None

    def _flight_items(self, itinerary: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [i for i in itinerary if i.get("item_type") == "flight"]

    def _meeting_item(self, itinerary: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for i in itinerary:
            if i.get("item_type") == "meeting":
                return i
        return None

    def input_validation_node(self, state: AdaptiveState) -> Dict[str, Any]:
        request = state["request"]
        missing: List[str] = []
        reflections: List[str] = []
        flags: List[str] = []

        for field in ("origin", "destination", "departure_date"):
            if not request.get(field):
                missing.append(f"{field} is required")

        if missing:
            reflections.append(f"Input validation failed: {', '.join(missing)}")
            return {
                "status": "awaiting_input",
                "missing_info": missing,
                "reflections": reflections,
                "logs": [self._log("input_validation", f"Missing fields: {missing}")],
            }

        dep_dt = parse_iso(request["departure_date"])
        if dep_dt is None:
            missing.append("departure_date must be YYYY-MM-DD format")
        ret_dt = parse_iso(request.get("return_date")) if request.get("return_date") else None
        if ret_dt and dep_dt and ret_dt.date() < dep_dt.date():
            missing.append("return_date must be on or after departure_date")
        if request.get("travelers", 1) < 1:
            missing.append("travelers must be >= 1")
        if request.get("budget") is not None and request["budget"] <= 0:
            missing.append("budget must be a positive number")

        text_to_check = " ".join(
            str(v) for v in [request.get("origin"), request.get("destination"), request.get("user_context", "")]
        )
        check = self.safety.check_input(text_to_check)
        flags.extend(check["flags"])

        if missing:
            return {
                "status": "awaiting_input",
                "missing_info": missing,
                "reflections": [f"Input validation failed: {', '.join(missing)}"],
                "safety_flags": flags,
                "logs": [self._log("input_validation", f"Invalid input: {missing}")],
            }
        if not check["allowed"]:
            return {
                "status": "awaiting_input",
                "missing_info": ["Security check failed"],
                "safety_flags": flags,
                "reflections": ["Security guard blocked input due to prompt injection pattern."],
                "logs": [self._log("input_validation", "Security check failed")],
            }

        req = FlightPlanRequest.from_dict(request)
        itinerary, assumptions, missing_info = build_itinerary(req, self.world)
        if not itinerary:
            return {
                "status": "awaiting_input",
                "itinerary": [],
                "missing_info": missing_info,
                "reflections": ["Planner could not generate any itinerary step."] + assumptions,
                "logs": [self._log("planner", "No itinerary generated")],
            }

        bookable = [i for i in itinerary if i["item_type"] in ("flight", "hotel")]
        user_confirmed = bool(request.get("confirm_irreversible", False))
        if bookable and not user_confirmed:
            reflections.append("Itinerary generated but requires user confirmation before booking flights/hotels.")
            return {
                "status": "awaiting_confirmation",
                "itinerary": itinerary,
                "desires": [d.to_dict() for d in self._build_desires(req)],
                "missing_info": missing_info,
                "requires_confirmation": True,
                "user_confirmed": False,
                "reflections": reflections,
                "safety_flags": flags + (["requires_confirmation"] if not user_confirmed else []),
                "logs": [self._log("input_validation", "Awaiting confirmation for irreversible bookings")],
            }

        desires = self._build_desires(req)
        reflections.append("Input validated successfully.")
        reflections.append(f"Initial itinerary has {len(itinerary)} steps.")

        return {
            "status": "booking",
            "itinerary": itinerary,
            "desires": [d.to_dict() for d in desires],
            "missing_info": missing_info,
            "user_confirmed": user_confirmed,
            "reflections": reflections,
            "safety_flags": flags,
            "logs": [self._log("input_validation", "Input validated"), self._log("planner", f"Generated {len(itinerary)} itinerary items")],
        }

    def _build_desires(self, request: FlightPlanRequest) -> List[Desire]:
        prefs = request.preferences or {}
        desires = [
            Desire(goal="Arrive on time for all scheduled commitments", priority=9 if prefs.get("meeting_time") else 7),
            Desire(goal="Avoid flight delays", priority=8),
            Desire(goal="Stay within budget", priority=7 if request.budget is not None else 4),
            Desire(goal="Travel comfortably", priority=4),
        ]
        return desires

    def book_itinerary_node(self, state: AdaptiveState) -> Dict[str, Any]:
        itinerary = self._itinerary_copy(state)
        reflections: List[str] = []
        logs: List[Dict[str, Any]] = []
        errors = 0

        for item in itinerary:
            if item.get("status") != "PENDING":
                continue
            if item["item_type"] == "flight":
                result = self.world.book_flight(item["id"])
            elif item["item_type"] == "hotel":
                result = self.world.book_hotel(item["id"])
            else:
                item["status"] = "BOOKED"
                item["confirmation"] = f"{item['id']}-{now_iso()}"
                reflections.append(f"{item['id']} confirmed (no external booking needed).")
                continue

            if result.get("status") == "BOOKED":
                item["status"] = "BOOKED"
                item["confirmation"] = result["confirmation"]
                reflections.append(f"{item['id']} booked successfully.")
                logs.append(self._log("book_itinerary", f"Booked {item['id']}", item["id"]))
            else:
                item["status"] = "FAILED"
                errors += 1
                msg = result.get("message", result.get("error", "unknown"))
                reflections.append(f"{item['id']} booking failed: {msg}")
                logs.append(self._log("book_itinerary", f"Failed to book {item['id']}: {msg}", item["id"]))

        return {
            "status": "perceiving",
            "itinerary": itinerary,
            "reflections": reflections,
            "logs": logs,
            "error_count": errors,
        }

    def perceive_node(self, state: AdaptiveState) -> Dict[str, Any]:
        itinerary = self._itinerary_copy(state)
        reflections: List[str] = []
        beliefs: List[Dict[str, Any]] = []
        logs: List[Dict[str, Any]] = []

        if not state["request"].get("predict_delays", True):
            reflections.append("Delay prediction disabled; relying on world status only.")
            return {"status": "deliberating", "reflections": reflections, "logs": logs}

        flight_items = self._flight_items(itinerary)
        if not flight_items:
            reflections.append("No flights to predict.")
            return {"status": "deliberating", "reflections": reflections, "logs": logs}

        result = self.predictor.predict(flight_items)
        logs.append(self._log("perceive", f"Predictor source={result['source']}, success={result['success']}"))

        for pred in result.get("predictions", []):
            idx = pred.get("flight_index", 0)
            if idx >= len(flight_items):
                continue
            flight = flight_items[idx]
            prob = float(pred.get("delay_probability", 0.0))
            minutes = int(pred.get("predicted_delay_minutes", 0))
            confidence = float(pred.get("confidence", 0.85))
            source = result["source"]
            fallback = pred.get("fallback", False)

            fact = (
                f"Flight {flight['id']} has delay probability {prob*100:.1f}% "
                f"with predicted delay {minutes} minutes (source: {source})."
            )
            beliefs.append(
                Belief(
                    fact=fact,
                    certainty=confidence if fallback else min(1.0, max(0.0, prob + 0.1)),
                    source=source,
                    topic="delay",
                ).to_dict()
            )
            flight["details"]["prediction"] = pred
            reflections.append(
                f"Observed {flight['id']}: delay probability {prob*100:.1f}%, predicted delay {minutes}m."
            )

        if not result["success"]:
            reflections.append("Delay predictor API unavailable; agent will use fallback assumptions.")
            beliefs.append(
                Belief(
                    fact="External delay predictor is unavailable; relying on fallback assumptions.",
                    certainty=0.5,
                    source="fallback",
                    topic="delay",
                ).to_dict()
            )

        return {
            "status": "deliberating",
            "itinerary": itinerary,
            "beliefs": beliefs,
            "reflections": reflections,
            "logs": logs,
        }

    def deliberate_node(self, state: AdaptiveState) -> Dict[str, Any]:
        desires = self._desires_copy(state)
        itinerary = self._itinerary_copy(state)
        beliefs = state.get("beliefs", [])
        experiences = state.get("experiences", [])
        reflections: List[str] = []

        for d in desires:
            d["threatened"] = False

        threshold = get_config().predictor.high_delay_threshold

        def effective_delay_prob(flight_item: Dict[str, Any], belief: Dict[str, Any]) -> float:
            prob = belief.get("certainty", 0.0)
            airline = flight_item.get("details", {}).get("airline", "")
            rel = self._airline_reliability(airline, experiences)
            return min(1.0, prob + (1.0 - rel) * 0.25)

        offending_flight: Optional[Dict[str, Any]] = None
        max_effective_prob = 0.0

        for flight in self._flight_items(itinerary):
            pred = flight.get("details", {}).get("prediction", {})
            if not pred:
                continue
            belief = next(
                (b for b in beliefs if flight["id"] in b.get("fact", "")),
                None,
            )
            if not belief:
                continue
            eff_prob = effective_delay_prob(flight, belief)
            minutes = int(pred.get("predicted_delay_minutes", 0))
            if eff_prob > max_effective_prob:
                max_effective_prob = eff_prob
                offending_flight = flight

            if eff_prob >= threshold:
                self._mark_desire(desires, "Avoid flight delays", threatened=True)
                reflections.append(
                    f"Desire 'Avoid flight delays' threatened by {flight['id']} (effective delay probability {eff_prob*100:.1f}%)."
                )

            meeting = self._meeting_item(itinerary)
            if meeting and flight["step"] in meeting.get("dependencies", []):
                arrival = parse_iso(flight["end_time"])
                if arrival:
                    delayed_arrival = arrival + timedelta(minutes=minutes)
                    meeting_start = parse_iso(meeting["start_time"])
                    buffer = int(flight.get("details", {}).get("meeting_buffer_minutes", 120))
                    if meeting_start and (delayed_arrival + timedelta(minutes=buffer)) > meeting_start:
                        self._mark_desire(desires, "Arrive on time for all scheduled commitments", threatened=True)
                        reflections.append(
                            f"Desire 'Arrive on time' threatened: predicted delay on {flight['id']} would miss the meeting."
                        )

        budget = state["request"].get("budget")
        if budget is not None:
            total = sum(i.get("cost", 0.0) for i in itinerary)
            if total > budget:
                self._mark_desire(desires, "Stay within budget", threatened=True)
                reflections.append(f"Desire 'Stay within budget' threatened: {total:.2f} exceeds {budget:.2f}.")

        strategy = "finalize"
        target_flight_id = None
        threatened = [d for d in desires if d.get("threatened")]
        if threatened:
            goal = sorted(threatened, key=lambda d: -d["priority"])[0]["goal"]
            if "Arrive on time" in goal and offending_flight:
                strategy = "rebook_flight"
                target_flight_id = offending_flight["id"]
            elif "Avoid flight delays" in goal and offending_flight:
                strategy = "rebook_flight"
                target_flight_id = offending_flight["id"]
            elif "Stay within budget" in goal:
                strategy = "reduce_cost"
            else:
                strategy = "wait_and_monitor"

        world_state = dict(state.get("world_state", {}))
        world_state["selected_strategy"] = strategy
        world_state["target_flight_id"] = target_flight_id
        world_state["max_effective_delay_prob"] = max_effective_prob

        reflections.append(f"Deliberation selected strategy: {strategy}")

        return {
            "status": "intending",
            "desires": desires,
            "world_state": world_state,
            "reflections": reflections,
            "logs": [self._log("deliberate", f"Strategy={strategy}, target_flight={target_flight_id}")],
        }

    def _mark_desire(
        self,
        desires: List[Dict[str, Any]],
        goal_substring: str,
        threatened: Optional[bool] = None,
        satisfied: Optional[bool] = None,
    ) -> None:
        for d in desires:
            if goal_substring in d["goal"]:
                if threatened is not None:
                    d["threatened"] = threatened
                if satisfied is not None:
                    d["satisfied"] = satisfied

    def _airline_reliability(self, airline: str, experiences: List[Dict[str, Any]]) -> float:
        if not airline:
            return 1.0
        relevant = [e for e in experiences if airline in e.get("context", "")]
        if not relevant:
            return 1.0
        avg = sum(e.get("utility", 0.0) for e in relevant) / len(relevant)
        return 0.5 + 0.5 * max(-1.0, min(1.0, avg))

    def intend_node(self, state: AdaptiveState) -> Dict[str, Any]:
        strategy = state["world_state"].get("selected_strategy", "finalize")
        target_flight_id = state["world_state"].get("target_flight_id")
        itinerary = self._itinerary_copy(state)
        intentions: List[Dict[str, Any]] = []
        reflections: List[str] = []

        if strategy == "finalize":
            intentions.append(
                Intention(
                    plan_name="Finalize itinerary",
                    action="finalize",
                    target_desire="All desires satisfied",
                    reasoning="No threatened desires; itinerary is consistent.",
                ).to_dict()
            )
        elif strategy == "rebook_flight" and target_flight_id:
            flight = self._find_item(itinerary, target_flight_id)
            if flight:
                pred = flight.get("details", {}).get("prediction", {})
                minutes = int(pred.get("predicted_delay_minutes", 0))
                arrival = parse_iso(flight["end_time"])
                after = (arrival + timedelta(minutes=minutes)).isoformat() if arrival else flight["end_time"]
                details = flight.get("details", {})
                origin = details.get("origin", "")
                destination = details.get("destination", "")
                date = flight["start_time"][:10]
                intentions.append(
                    Intention(
                        plan_name=f"Rebook {target_flight_id} to avoid predicted delay",
                        action="rebook_flight",
                        target_desire="Arrive on time for all scheduled commitments",
                        params={
                            "old_flight_id": target_flight_id,
                            "origin": origin,
                            "destination": destination,
                            "date": date,
                            "after": after,
                            "reason": f"Predicted delay {minutes}m",
                        },
                        reasoning=(
                            f"Flight {target_flight_id} has a predicted delay that threatens the meeting. "
                            "Rebooking to a later flight restores the alignment between beliefs and desires."
                        ),
                    ).to_dict()
                )
                reflections.append(f"Formed intention to rebook {target_flight_id}.")
        elif strategy == "reduce_cost":
            intentions.append(
                Intention(
                    plan_name="Reduce itinerary cost",
                    action="reduce_cost",
                    target_desire="Stay within budget",
                    reasoning="Current itinerary exceeds budget; seek cheaper alternatives.",
                ).to_dict()
            )
            reflections.append("Formed intention to reduce cost.")
        elif strategy == "wait_and_monitor":
            intentions.append(
                Intention(
                    plan_name="Wait and monitor flight status",
                    action="wait_and_monitor",
                    target_desire="Avoid flight delays",
                    reasoning="Delay probability is moderate and does not currently threaten commitments.",
                ).to_dict()
            )
            reflections.append("Formed intention to wait and monitor.")

        return {
            "status": "executing",
            "intentions": intentions,
            "reflections": reflections,
            "logs": [self._log("intend", f"Formed {len(intentions)} intention(s) for strategy {strategy}")],
        }

    def execute_node(self, state: AdaptiveState) -> Dict[str, Any]:
        itinerary = self._itinerary_copy(state)
        intentions = self._intentions_copy(state)
        reflections: List[str] = []
        beliefs: List[Dict[str, Any]] = []
        logs: List[Dict[str, Any]] = []
        missing_info = list(state.get("missing_info", []))
        user_confirmed = state.get("user_confirmed", False)

        for intent in intentions:
            if intent.get("status") != "FORMULATED":
                continue

            action = intent.get("action", "")
            safety = self.safety.check_action(action, user_confirmed)
            if not safety["allowed"]:
                return {
                    "status": "awaiting_confirmation",
                    "requires_confirmation": True,
                    "intentions": intentions,
                    "reflections": [f"Execution paused: {intent['plan_name']} requires user confirmation."],
                    "safety_flags": safety["flags"],
                    "logs": [self._log("execute", f"Requires confirmation for {intent['plan_name']}")],
                }

            intent["status"] = "EXECUTING"
            logs.append(self._log("execute", f"Executing {intent['plan_name']}", intent.get("plan_name", "")))

            if action == "finalize" or action == "wait_and_monitor":
                intent["status"] = "COMPLETED"
                reflections.append(f"{intent['plan_name']} completed (no external action needed).")
                beliefs.append(
                    Belief(
                        fact=f"Intention '{intent['plan_name']}' completed without external changes.",
                        certainty=1.0,
                        source="bdi_execution",
                        topic="status",
                    ).to_dict()
                )

            elif action == "rebook_flight":
                params = intent.get("params", {})
                old_id = params.get("old_flight_id")
                result = self.world.rebook_flight(
                    old_id,
                    params.get("origin", ""),
                    params.get("destination", ""),
                    params.get("date", ""),
                    after=params.get("after"),
                )
                if result.get("status") == "REBOOKED":
                    new_flight = result["flight"]
                    flight_item = self._find_item(itinerary, old_id)
                    if flight_item:
                        flight_item["id"] = new_flight["flight_id"]
                        flight_item["details"] = new_flight
                        flight_item["action"] = f"Rebooked flight {new_flight['flight_id']} due to {params.get('reason')}"
                        flight_item["start_time"] = new_flight["departure"]
                        flight_item["end_time"] = new_flight["arrival"]
                        flight_item["cost"] = round(new_flight["price_usd"] * max(1, state["request"].get("travelers", 1)), 2)
                        flight_item["status"] = "BOOKED"
                        flight_item["confirmation"] = result["confirmation"]
                        flight_item["notes"].append(f"Rebooked from {old_id}: {params.get('reason')}")
                    self._propagate_changes(itinerary, flight_item)
                    intent["status"] = "COMPLETED"
                    reflections.append(
                        f"Rebook successful: {old_id} -> {new_flight['flight_id']} ({params.get('reason')})."
                    )
                    beliefs.append(
                        Belief(
                            fact=f"Flight rebooked from {old_id} to {new_flight['flight_id']} with confirmation {result['confirmation']}.",
                            certainty=1.0,
                            source="bdi_execution",
                            topic="availability",
                        ).to_dict()
                    )
                else:
                    intent["status"] = "ABORTED"
                    missing_info.append(f"Could not rebook {old_id}: {result.get('message')}")
                    reflections.append(f"Rebook failed for {old_id}: {result.get('message')}")
                    beliefs.append(
                        Belief(
                            fact=f"Rebooking {old_id} failed: {result.get('message')}",
                            certainty=1.0,
                            source="bdi_execution",
                            topic="availability",
                        ).to_dict()
                    )

            elif action == "reduce_cost":
                reduced = self._try_reduce_cost(itinerary, state["request"])
                if reduced:
                    intent["status"] = "COMPLETED"
                    reflections.append("Cost reduction intention completed.")
                else:
                    intent["status"] = "ABORTED"
                    missing_info.append("Could not reduce cost within constraints.")
                    reflections.append("Cost reduction intention aborted: no cheaper alternatives.")

            elif action == "escalate":
                intent["status"] = "ABORTED"
                missing_info.append("Human escalation required: agent could not resolve the situation autonomously.")
                reflections.append("Escalated to human operator.")

            else:
                intent["status"] = "ABORTED"
                reflections.append(f"Unknown action {action}; intention aborted.")

        return {
            "status": "reviewing",
            "itinerary": itinerary,
            "intentions": intentions,
            "beliefs": beliefs,
            "missing_info": missing_info,
            "reflections": reflections,
            "logs": logs,
        }

    def _propagate_changes(self, itinerary: List[Dict[str, Any]], changed_flight: Optional[Dict[str, Any]]) -> None:
        if not changed_flight:
            return
        changed_step = changed_flight["step"]
        new_arrival = parse_iso(changed_flight["end_time"])
        if not new_arrival:
            return
        for item in itinerary:
            if changed_step not in item.get("dependencies", []):
                continue
            if item["item_type"] == "meeting":
                buffer = int(item.get("details", {}).get("meeting_buffer_minutes", 120))
                new_start = new_arrival + timedelta(minutes=buffer)
                item["start_time"] = new_start.isoformat()
                item["end_time"] = (new_start + timedelta(minutes=60)).isoformat()
                item["details"]["time"] = new_start.strftime("%H:%M")
                item["notes"].append(f"Rescheduled due to rebooking of {changed_flight['id']}")
            elif item["item_type"] == "hotel":
                old_checkin = parse_iso(item["start_time"])
                if old_checkin and new_arrival.date() > old_checkin.date():
                    item["start_time"] = f"{new_arrival.date().isoformat()}T15:00:00"
                    item["notes"].append(f"Check-in updated due to rebooking of {changed_flight['id']}")

    def _try_reduce_cost(self, itinerary: List[Dict[str, Any]], request: Dict[str, Any]) -> bool:
        flights = self._flight_items(itinerary)
        if not flights:
            return False
        costliest = max(flights, key=lambda x: x["cost"])
        details = costliest.get("details", {})
        alternatives = self.world.search_flights(
            details.get("origin", ""),
            details.get("destination", ""),
            costliest["start_time"][:10],
        )
        current_price = details.get("price_usd", float("inf"))
        cheaper = [a for a in alternatives if a["price_usd"] < current_price and a["flight_id"] != costliest["id"]]
        if not cheaper:
            return False
        best = min(cheaper, key=lambda a: a["price_usd"])
        result = self.world.rebook_flight(
            costliest["id"],
            details.get("origin", ""),
            details.get("destination", ""),
            costliest["start_time"][:10],
        )
        if result.get("status") == "REBOOKED":
            new_flight = result["flight"]
            costliest["id"] = new_flight["flight_id"]
            costliest["details"] = new_flight
            costliest["start_time"] = new_flight["departure"]
            costliest["end_time"] = new_flight["arrival"]
            costliest["cost"] = round(new_flight["price_usd"] * max(1, request.get("travelers", 1)), 2)
            costliest["status"] = "BOOKED"
            costliest["confirmation"] = result["confirmation"]
            costliest["notes"].append(f"Rebooked to cheaper alternative {new_flight['flight_id']}")
            self._propagate_changes(itinerary, costliest)
            return True
        return False

    def review_node(self, state: AdaptiveState) -> Dict[str, Any]:
        desires = self._desires_copy(state)
        itinerary = self._itinerary_copy(state)
        reflections: List[str] = []

        for d in desires:
            d["threatened"] = False
            d["satisfied"] = False

        for flight in self._flight_items(itinerary):
            pred = flight.get("details", {}).get("prediction", {})
            prob = float(pred.get("delay_probability", 0.0))
            minutes = int(pred.get("predicted_delay_minutes", 0))
            if prob >= get_config().predictor.high_delay_threshold:
                self._mark_desire(desires, "Avoid flight delays", threatened=True)
                reflections.append(f"Review: {flight['id']} still has high delay probability {prob*100:.1f}%.")
            meeting = self._meeting_item(itinerary)
            if meeting and flight["step"] in meeting.get("dependencies", []):
                arrival = parse_iso(flight["end_time"])
                if arrival:
                    delayed_arrival = arrival + timedelta(minutes=minutes)
                    meeting_start = parse_iso(meeting["start_time"])
                    buffer = int(flight.get("details", {}).get("meeting_buffer_minutes", 120))
                    if meeting_start and (delayed_arrival + timedelta(minutes=buffer)) > meeting_start:
                        self._mark_desire(desires, "Arrive on time for all scheduled commitments", threatened=True)
                        reflections.append(f"Review: predicted delay on {flight['id']} still threatens meeting.")

        budget = state["request"].get("budget")
        if budget is not None:
            total = sum(i.get("cost", 0.0) for i in itinerary)
            if total > budget:
                self._mark_desire(desires, "Stay within budget", threatened=True)
                reflections.append(f"Review: cost {total:.2f} still exceeds budget {budget:.2f}.")
            else:
                self._mark_desire(desires, "Stay within budget", satisfied=True)
                reflections.append(f"Review: cost {total:.2f} within budget {budget:.2f}.")

        if not any("Arrive on time" in d["goal"] and d["threatened"] for d in desires):
            self._mark_desire(desires, "Arrive on time for all scheduled commitments", satisfied=True)

        if not any("Avoid flight delays" in d["goal"] and d["threatened"] for d in desires):
            self._mark_desire(desires, "Avoid flight delays", satisfied=True)

        if itinerary:
            self._mark_desire(desires, "Travel comfortably", satisfied=True)

        all_satisfied = all(d.get("satisfied") for d in desires)
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", self.config.max_retries)

        if all_satisfied:
            status = "adapting"
            reflections.append("All BDI desires satisfied. Proceeding to adaptive personalization.")
        elif retry_count < max_retries:
            status = "deliberating"
            retry_count += 1
            reflections.append(f"Desires not fully satisfied. Re-deliberating (retry {retry_count}/{max_retries}).")
        else:
            status = "adapting"
            reflections.append("Max retries reached; proceeding to adaptive personalization.")

        return {
            "status": status,
            "desires": desires,
            "retry_count": retry_count,
            "reflections": reflections,
            "logs": [self._log("review", f"Status={status}, all_satisfied={all_satisfied}")],
        }

    def learn_node(self, state: AdaptiveState) -> Dict[str, Any]:
        if not state["request"].get("enable_learning", True):
            return {"status": "adapting", "reflections": ["BDI learning disabled."]}

        experiences = copy.deepcopy(state.get("experiences", []))
        reflections: List[str] = []
        itinerary = state.get("itinerary", [])

        for intent in state.get("intentions", []):
            if intent.get("action") in ("finalize", "wait_and_monitor"):
                continue
            action = intent.get("action", "")
            target = intent.get("target_desire", "")
            params = intent.get("params", {})
            status = intent.get("status", "ABORTED")

            context_parts = [f"action={action}", f"target={target}"]
            if action == "rebook_flight":
                old_id = params.get("old_flight_id", "")
                flight = next((i for i in itinerary if i["id"] == old_id), None)
                if flight:
                    details = flight.get("details", {})
                    context_parts.append(
                        f"flight={old_id},airline={details.get('airline','')},route={details.get('origin','')}-{details.get('destination','')}"
                    )
            context = "; ".join(context_parts)

            outcome = "success" if status == "COMPLETED" else "failure"
            utility = 1.0 if status == "COMPLETED" else -1.0
            if status == "COMPLETED" and "Stay within budget" in target:
                budget = state["request"].get("budget")
                if budget is not None and sum(i.get("cost", 0.0) for i in itinerary) > budget:
                    utility -= 0.3

            experiences.append(
                Experience(
                    context=context,
                    action=action,
                    outcome=outcome,
                    utility=max(-1.0, min(1.0, utility)),
                ).to_dict()
            )
            reflections.append(f"Learned from {action}: outcome={outcome}, utility={utility:.2f}.")

        return {
            "status": "adapting",
            "experiences": experiences,
            "reflections": reflections,
            "logs": [self._log("learn", f"Recorded {len(experiences)} experience(s)")],
        }
