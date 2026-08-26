"""Nodos del grafo LangGraph para UC-259."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta
from typing import Any, Dict, List

from config import AgentConfig, get_config
from models import FlightPlanRequest, now_iso, parse_iso
from planner import build_itinerary
from safety import SafetyGuard
from state import AgentState
from world_simulator import WorldSimulator


class AgentNodes:
    """Contenedor con estado compartido (mundo, seguridad, config) para los nodos."""

    def __init__(
        self,
        world: WorldSimulator,
        config: AgentConfig,
        safety: SafetyGuard,
    ) -> None:
        self.world = world
        self.config = config
        self.safety = safety

    # --------------------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------------------
    def _log(self, node: str, message: str, item_id: str = "") -> Dict[str, Any]:
        return {"node": node, "item_id": item_id, "message": message, "timestamp": now_iso()}

    def _itinerary_copy(self, state: AgentState) -> List[Dict[str, Any]]:
        return copy.deepcopy(state["itinerary"])

    def _find_item(self, itinerary: List[Dict[str, Any]], item_id: str) -> Optional[Dict[str, Any]]:
        for item in itinerary:
            if item["id"] == item_id:
                return item
        return None

    # --------------------------------------------------------------------------
    # Nodo 1: Validación de entrada y seguridad
    # --------------------------------------------------------------------------
    def input_validation_node(self, state: AgentState) -> Dict[str, Any]:
        request = state["request"]
        missing: List[str] = []
        reflections: List[str] = []
        flags: List[str] = []

        # Validación de campos obligatorios
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

        # Fechas coherentes
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

        # Chequeo de seguridad sobre texto libre
        text_to_check = " ".join(
            str(v)
            for v in [request.get("origin"), request.get("destination"), request.get("user_goal", "")]
        )
        check = self.safety.check_input(text_to_check)
        flags.extend(check["flags"])

        if missing:
            return {
                "status": "awaiting_input",
                "missing_info": missing,
                "reflections": [f"Input validation failed: {', '.join(missing)}"],
                "safety_flags": flags,
                "logs": [self._log("input_validation", f"Missing fields: {missing}")],
            }

        if not check["allowed"]:
            return {
                "status": "awaiting_input",
                "missing_info": ["Security check failed"],
                "safety_flags": flags,
                "reflections": ["Security guard blocked input due to prompt injection pattern."],
                "logs": [self._log("input_validation", "Security check failed", item_id="")],
            }

        reflections.append("Input validated successfully.")
        return {
            "status": "planning",
            "user_confirmed": bool(request.get("confirm_irreversible", False)),
            "reflections": reflections,
            "safety_flags": flags,
            "logs": [self._log("input_validation", "Input validated")],
        }

    # --------------------------------------------------------------------------
    # Nodo 2: Planificación proactiva
    # --------------------------------------------------------------------------
    def planner_node(self, state: AgentState) -> Dict[str, Any]:
        request = FlightPlanRequest.from_dict(state["request"])
        itinerary, assumptions, missing_info = build_itinerary(request, self.world)

        reflections = [
            f"Planner generated {len(itinerary)} initial steps.",
            *assumptions,
        ]

        if not itinerary:
            return {
                "status": "awaiting_input",
                "itinerary": [],
                "missing_info": missing_info,
                "reflections": reflections,
                "logs": [self._log("planner", "No itinerary could be generated")],
            }

        return {
            "status": "executing",
            "itinerary": itinerary,
            "missing_info": missing_info,
            "reflections": reflections,
            "logs": [self._log("planner", f"Generated itinerary with {len(itinerary)} items")],
        }

    # --------------------------------------------------------------------------
    # Nodo 3: Ejecutor con seguridad y retries
    # --------------------------------------------------------------------------
    def executor_node(self, state: AgentState) -> Dict[str, Any]:
        itinerary = self._itinerary_copy(state)
        reflections: List[str] = []
        logs: List[Dict[str, Any]] = []
        last_actioned = ""

        for item in itinerary:
            if item.get("status") != "PENDING":
                continue

            action_name = {
                "flight": "book_flight",
                "hotel": "book_hotel",
                "meeting": "schedule_meeting",
                "car": "book_car",
            }.get(item["item_type"], item["item_type"])

            # Seguridad: acciones irreversibles requieren confirmación
            safety = self.safety.check_action(action_name, state["user_confirmed"])
            if not safety["allowed"]:
                return {
                    "status": "awaiting_confirmation",
                    "requires_confirmation": True,
                    "itinerary": itinerary,
                    "reflections": [f"Execution paused: {item['id']} requires user confirmation."],
                    "safety_flags": safety["flags"],
                    "logs": [self._log("executor", f"Requires confirmation for {item['id']}", item["id"])],
                }

            try:
                if item["item_type"] == "flight":
                    result = self.world.book_flight(item["id"], item["details"])
                elif item["item_type"] == "hotel":
                    result = self.world.book_hotel(item["id"], item["details"])
                elif item["item_type"] == "meeting":
                    result = {
                        "status": "BOOKED",
                        "confirmation": f"MTG-{item['id']}-{now_iso()}",
                    }
                elif item["item_type"] == "car":
                    result = {"status": "BOOKED", "confirmation": f"CAR-{item['id']}"}
                else:
                    result = {"status": "FAILED", "error": "unknown_item_type"}
            except Exception as exc:
                result = {"status": "FAILED", "error": str(exc)}

            logs.append(self._log("executor", f"Executed {item['id']}: {result['status']}", item["id"]))

            if result.get("status") in ("BOOKED", "REBOOKED", "SCHEDULED"):
                item["status"] = result["status"]
                item["confirmation"] = result.get("confirmation")
                reflections.append(f"{item['id']} booked successfully.")
                last_actioned = item["id"]
            else:
                item["status"] = "FAILED"
                item["notes"].append(f"Execution error: {result.get('error') or result.get('message', '')}")
                reflections.append(f"{item['id']} failed: {result.get('error') or result.get('message', '')}")
                last_actioned = item["id"]

        return {
            "status": "monitoring",
            "itinerary": itinerary,
            "world_state": {**state.get("world_state", {}), "last_actioned": last_actioned},
            "reflections": reflections,
            "logs": logs,
        }

    # --------------------------------------------------------------------------
    # Nodo 4: Monitoreo y reflexión
    # --------------------------------------------------------------------------
    def monitor_reflect_node(self, state: AgentState) -> Dict[str, Any]:
        itinerary = self._itinerary_copy(state)
        reflections: List[str] = []
        needs_correction = False
        failed_items = [i for i in itinerary if i.get("status") == "FAILED"]

        if failed_items:
            reflections.append(f"Detected {len(failed_items)} failed bookings; correction needed.")
            needs_correction = True

        # Consultar estado de vuelos reservados/rebooked
        for item in itinerary:
            if item["item_type"] != "flight" or item.get("status") not in ("BOOKED", "REBOOKED"):
                continue
            status = self.world.check_status(item["id"])
            event_type = status.get("status", "ON_TIME")
            if event_type != "ON_TIME":
                item["status"] = event_type  # DELAYED, CANCELLED, OVERBOOKED
                item["notes"].append(
                    f"Real-world event: {event_type}. Details: {status.get('reason') or status.get('delay_minutes', '')}"
                )
                reflections.append(
                    f"Flight {item['id']} is {event_type}. Plan consistency must be re-evaluated."
                )
                needs_correction = True

        # Consistencia temporal: propagación de impacto hacia adelante
        for item in itinerary:
            if item["status"] == "DELAYED":
                delay_min = self.world._events.get(item["id"], {}).get("delay_minutes", 0)
                self._propagate_delay(itinerary, item, delay_min)
                reflections.append(
                    f"Propagated {delay_min} minute delay from {item['id']} to downstream items."
                )
                needs_correction = True

        # Decidir siguiente paso
        all_terminal = all(
            i.get("status") in ("BOOKED", "REBOOKED", "SCHEDULED", "SKIPPED")
            for i in itinerary
        )
        if needs_correction:
            new_status = "correcting"
        elif all_terminal:
            new_status = "done"
        else:
            new_status = "executing"

        return {
            "status": new_status,
            "itinerary": itinerary,
            "reflections": reflections,
            "logs": [self._log("monitor_reflect", f"Status after monitoring: {new_status}")],
        }

    def _propagate_delay(
        self,
        itinerary: List[Dict[str, Any]],
        changed_item: Dict[str, Any],
        delay_minutes: int,
    ) -> None:
        """Ajusta ítems dependientes del vuelo afectado usando la nueva hora de llegada."""
        changed_step = changed_item["step"]
        new_arrival_str = changed_item["details"].get("arrival")
        if new_arrival_str:
            new_arrival = parse_iso(new_arrival_str) or datetime.fromisoformat(new_arrival_str)
            new_arrival += timedelta(minutes=delay_minutes)
        else:
            return

        for item in itinerary:
            if changed_step not in item.get("dependencies", []):
                continue
            if item["item_type"] == "meeting":
                old_start = parse_iso(item["start_time"])
                if old_start:
                    new_start = new_arrival + timedelta(minutes=120)
                    item["start_time"] = new_start.isoformat()
                    item["end_time"] = (new_start + timedelta(minutes=60)).isoformat()
                    item["status"] = "PENDING"
                    item["notes"].append(f"Rescheduled due to delay on {changed_item['id']}")
            elif item["item_type"] == "hotel":
                old_checkin = parse_iso(item["start_time"])
                if old_checkin and new_arrival.date() > old_checkin.date():
                    item["start_time"] = f"{new_arrival.date().isoformat()}T15:00:00"
                    item["notes"].append(f"Check-in updated due to delay on {changed_item['id']}")

    # --------------------------------------------------------------------------
    # Nodo 5: Autocorrección
    # --------------------------------------------------------------------------
    def self_corrector_node(self, state: AgentState) -> Dict[str, Any]:
        itinerary = self._itinerary_copy(state)
        reflections: List[str] = []
        missing_info = list(state.get("missing_info", []))

        for item in itinerary:
            if item["status"] in ("DELAYED", "CANCELLED", "OVERBOOKED") and item["item_type"] == "flight":
                details = item["details"]
                origin = details.get("origin", "")
                destination = details.get("destination", "")
                date = details.get("departure", "")[:10]
                after = details.get("arrival")
                if item["status"] == "DELAYED":
                    delay = self.world._events.get(item["id"], {}).get("delay_minutes", 180)
                    after_dt = parse_iso(after)
                    if after_dt:
                        after = (after_dt + timedelta(minutes=delay)).isoformat()
                    reason = f"delayed {delay} minutes"
                else:
                    reason = item["status"].lower()

                result = self.world.rebook_flight(item["id"], origin, destination, date, after=after)
                if result.get("status") == "REBOOKED":
                    new_flight = result["flight"]
                    item["id"] = new_flight["flight_id"]
                    item["details"] = new_flight
                    item["action"] = f"Rebooked flight due to {reason}: {new_flight['flight_id']}"
                    item["status"] = "PENDING"
                    item["cost"] = new_flight["price_usd"] * max(1, state["request"].get("travelers", 1))
                    item["start_time"] = new_flight["departure"]
                    item["end_time"] = new_flight["arrival"]
                    item["confirmation"] = None
                    item["notes"].append(f"Rebooked to {new_flight['flight_id']} because original was {reason}")
                    reflections.append(
                        f"Rebooked {details.get('flight_id', 'flight')} -> {new_flight['flight_id']} ({reason})."
                    )
                else:
                    item["status"] = "FAILED"
                    item["notes"].append(f"Unable to rebook: {result.get('message')}")
                    missing_info.append(f"No alternative flight for {details.get('flight_id')} on {date}.")
                    reflections.append(f"Could not rebook {item.get('id')}: {result.get('message')}")

            elif item["status"] == "FAILED":
                # Intento simple de alternativa por tipo
                if item["item_type"] == "hotel":
                    item["notes"].append("Retrying hotel booking with next available option.")
                    item["status"] = "PENDING"
                else:
                    item["notes"].append("Marked for retry in next execution cycle.")
                    item["status"] = "PENDING"

        return {
            "status": "executing",
            "itinerary": itinerary,
            "missing_info": missing_info,
            "reflections": reflections,
            "logs": [self._log("self_corrector", "Applied corrections")],
        }

    # --------------------------------------------------------------------------
    # Nodo 6: Finalizador
    # --------------------------------------------------------------------------
    def finalizer_node(self, state: AgentState) -> Dict[str, Any]:
        itinerary = state.get("itinerary", [])
        total_cost = round(sum(i.get("cost", 0.0) for i in itinerary), 2)
        currency = state["request"].get("currency", "USD")

        status = state.get("status", "done")
        if state.get("missing_info"):
            # Si hay información crítica faltante y no se completó, marcar awaiting_input
            if status not in ("done", "awaiting_confirmation"):
                status = "awaiting_input"

        final_output = {
            "request_id": state["request"].get("request_id"),
            "status": status,
            "itinerary": itinerary,
            "total_cost": total_cost,
            "currency": currency,
            "reflections": state.get("reflections", []),
            "safety_flags": state.get("safety_flags", []),
            "missing_info": state.get("missing_info", []),
            "requires_confirmation": state.get("requires_confirmation", False),
            "error_count": state.get("error_count", 0),
            "retry_count": state.get("retry_count", 0),
        }

        return {
            "status": status,
            "final_output": final_output,
            "logs": [self._log("finalizer", f"Final status: {status}")],
        }
