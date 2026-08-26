"""Nodos adaptativos: perfil de usuario, control gate, aprendizaje y memoria de patrones."""
from __future__ import annotations

import copy
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

from langgraph.types import interrupt

from config import AgentConfig, MemoryConfig, get_config
from memory import PatternMemoryDB
from models import Belief, FlightPlanRequest, Recommendation, now_iso, parse_iso
from state import AdaptiveState


class AdaptiveNodes:
    """Capa adaptativa que estudia patrones de usuario, genera recomendaciones,
    aplica un control gate y aprende de las aprobaciones/rechazos."""

    def __init__(
        self,
        memory: PatternMemoryDB,
        config: AgentConfig,
        memory_config: MemoryConfig,
    ) -> None:
        self.memory = memory
        self.config = config
        self.memory_config = memory_config

    # --------------------------------------------------------------------------
    # Utilidades
    # --------------------------------------------------------------------------
    def _log(self, node: str, message: str, item_id: str = "") -> Dict[str, Any]:
        return {"node": node, "item_id": item_id, "message": message, "timestamp": now_iso()}

    def _profile_preferences(self, state: AdaptiveState) -> Dict[str, Any]:
        return state.get("profile", {}).get("preferences", {})

    def _pattern_score(self, state: AdaptiveState, key: str) -> float:
        return state.get("profile", {}).get("pattern_scores", {}).get(key, {}).get("score", 0.5)

    # --------------------------------------------------------------------------
    # Cargar/actualizar perfil de usuario
    # --------------------------------------------------------------------------
    def load_profile_node(self, state: AdaptiveState) -> Dict[str, Any]:
        user_id = state["request"].get("user_id", "anonymous")
        profile = self.memory.get_profile(user_id)

        # Fusionar preferencias explícitas de la request con las del perfil
        req_prefs = state["request"].get("preferences", {})
        merged = dict(profile.preferences)
        merged.update(req_prefs)
        profile.preferences = merged

        reflections = [f"Loaded profile for user {user_id}."]
        return {
            "profile": profile.to_dict(),
            "reflections": reflections,
            "logs": [self._log("load_profile", f"Profile loaded for {user_id}")],
        }

    # --------------------------------------------------------------------------
    # Generar recomendaciones personalizadas
    # --------------------------------------------------------------------------
    def generate_recommendations_node(self, state: AdaptiveState) -> Dict[str, Any]:
        itinerary = copy.deepcopy(state.get("itinerary", []))
        profile_prefs = self._profile_preferences(state)
        recommendations: List[Dict[str, Any]] = []
        reflections: List[str] = []

        def _action_id(category: str, item_id: str, action: str) -> str:
            return hashlib.md5(f"{category}:{item_id}:{action}".encode("utf-8")).hexdigest()[:12]

        # 1. Asiento de avión basado en patrón
        seat_pref = profile_prefs.get("seat")
        if seat_pref:
            for flight in itinerary:
                if flight.get("item_type") == "flight" and flight.get("status") == "BOOKED":
                    action_text = f"Reserve {seat_pref} seat for {flight['id']}"
                    recommendations.append(
                        Recommendation(
                            action_id=_action_id("flight", flight["id"], action_text),
                            item_id=flight["id"],
                            action=action_text,
                            reason=f"User historically prefers {seat_pref} seats.",
                            source_type="PATTERN_MATCH",
                            confidence=0.9,
                            cost_impact=0.0,
                            category="flight",
                        ).to_dict()
                    )
            reflections.append(f"Generated seat recommendation based on profile preference: {seat_pref}.")

        # 2. Hotel basado en cadena preferida
        hotel_chain = profile_prefs.get("hotel_chain")
        if hotel_chain:
            for hotel in itinerary:
                if hotel.get("item_type") == "hotel" and hotel.get("status") == "BOOKED":
                    action_text = f"Request upgrade/loyalty perks at {hotel_chain} for {hotel['id']}"
                    recommendations.append(
                        Recommendation(
                            action_id=_action_id("hotel", hotel["id"], action_text),
                            item_id=hotel["id"],
                            action=action_text,
                            reason=f"User prefers {hotel_chain} chain.",
                            source_type="PATTERN_MATCH",
                            confidence=0.8,
                            cost_impact=0.0,
                            category="hotel",
                        ).to_dict()
                    )
            reflections.append(f"Generated hotel-chain recommendation based on profile: {hotel_chain}.")

        # 3. Transporte: inferencia de IA si hora de llegada es pico
        for flight in itinerary:
            if flight.get("item_type") != "flight":
                continue
            arrival = parse_iso(flight.get("end_time"))
            if not arrival:
                continue
            hour = arrival.hour
            is_peak = 17 <= hour <= 20
            if is_peak:
                action_text = "Book helicopter transfer instead of taxi"
                recommendations.append(
                    Recommendation(
                        action_id=_action_id("transport", flight["id"], action_text),
                        item_id=flight["id"],
                        action=action_text,
                        reason=(
                            f"Peak-hour arrival ({hour}:00) at destination; traffic may cause delays. "
                            "Helicopter saves ~90 minutes."
                        ),
                        source_type="AI_INFERENCE",
                        confidence=0.75,
                        cost_impact=150.0,
                        category="transport",
                    ).to_dict()
                )
                reflections.append("Generated AI_INFERENCE transport recommendation due to peak-hour arrival.")
                break

        # 4. Restauración basada en restricción dietética
        dietary = profile_prefs.get("dietary")
        if dietary:
            action_text = f"Book table at a top-rated {dietary} restaurant"
            recommendations.append(
                Recommendation(
                    action_id=_action_id("dining", "dining-01", action_text),
                    item_id="dining-01",
                    action=action_text,
                    reason=f"User follows a {dietary} diet; proactively securing a matching restaurant.",
                    source_type="AI_INFERENCE",
                    confidence=0.7,
                    cost_impact=80.0,
                    category="dining",
                ).to_dict()
            )
            reflections.append(f"Generated dining recommendation for {dietary} diet.")

        return {
            "recommendations": recommendations,
            "reflections": reflections,
            "logs": [self._log("generate_recommendations", f"Generated {len(recommendations)} recommendation(s)")],
        }

    # --------------------------------------------------------------------------
    # Control Gate: separar acciones automáticas de las que requieren aprobación
    # --------------------------------------------------------------------------
    def control_gate_node(self, state: AdaptiveState) -> Dict[str, Any]:
        recommendations = copy.deepcopy(state.get("recommendations", []))
        approved_ids = set(state.get("approved_action_ids", []))
        rejected_ids = set(state.get("rejected_action_ids", []))
        auto_approve_all = bool(state["request"].get("auto_approve_all", False))
        auto_actions: List[Dict[str, Any]] = []
        approval_actions: List[Dict[str, Any]] = []
        reflections: List[str] = []

        threshold = self.memory_config.pattern_match_threshold
        cost_threshold = self.memory_config.auto_cost_threshold

        for rec in recommendations:
            pattern_score = self._pattern_score(state, rec["action"])
            confidence = rec.get("confidence", 0.5)
            cost = rec.get("cost_impact", 0.0)
            source = rec.get("source_type", "AI_INFERENCE")

            # Si el usuario ya aprobó explícitamente esta acción, ejecutarla
            if rec["action_id"] in approved_ids:
                rec["status"] = "PENDING_APPROVAL"  # se ejecutará en el siguiente nodo
                auto_actions.append(rec)
                reflections.append(f"User pre-approved {rec['action_id']}: {rec['action']}")
                continue

            # Si el usuario la rechazó previamente, saltarla
            if rec["action_id"] in rejected_ids:
                rec["status"] = "REJECTED"
                reflections.append(f"User pre-rejected {rec['action_id']}: {rec['action']}")
                continue

            # Zona de confianza: patrón conocido del perfil o confianza alta y coste bajo
            is_pattern_match = source == "PATTERN_MATCH" and confidence >= threshold and cost <= cost_threshold
            is_historically_trusted = source == "AI_INFERENCE" and pattern_score >= threshold and cost <= cost_threshold
            if is_pattern_match or is_historically_trusted or auto_approve_all:
                rec["status"] = "AUTO_EXECUTED"
                auto_actions.append(rec)
                reflections.append(f"Auto-approved ({source}): {rec['action']}")
            else:
                rec["status"] = "PENDING_APPROVAL"
                approval_actions.append(rec)
                reflections.append(f"Requires approval ({source}): {rec['action']}")

        return {
            "auto_actions": auto_actions,
            "approval_actions": approval_actions,
            "recommendations": recommendations,
            "reflections": reflections,
            "logs": [self._log("control_gate", f"Auto={len(auto_actions)}, Approval={len(approval_actions)}")],
        }

    # --------------------------------------------------------------------------
    # Ejecutar acciones automáticas
    # --------------------------------------------------------------------------
    def execute_auto_node(self, state: AdaptiveState) -> Dict[str, Any]:
        auto_actions = copy.deepcopy(state.get("auto_actions", []))
        itinerary = copy.deepcopy(state.get("itinerary", []))
        reflections: List[str] = []

        for rec in auto_actions:
            rec["status"] = "AUTO_EXECUTED"
            # Aplicar al itinerario como nota/coste
            item = next((i for i in itinerary if i["id"] == rec["item_id"]), None)
            if item:
                item["notes"].append(f"Auto-applied: {rec['action']} ({rec['reason']})")
                if rec.get("cost_impact", 0.0) > 0:
                    item["cost"] = round(item.get("cost", 0.0) + rec["cost_impact"], 2)
            reflections.append(f"Auto-executed {rec['action_id']}: {rec['action']}")

        return {
            "auto_actions": auto_actions,
            "itinerary": itinerary,
            "reflections": reflections,
            "logs": [self._log("execute_auto", f"Executed {len(auto_actions)} auto action(s)")],
        }

    # --------------------------------------------------------------------------
    # Manejar aprobaciones
    # --------------------------------------------------------------------------
    def approval_handler_node(self, state: AdaptiveState) -> Dict[str, Any]:
        approval_actions = copy.deepcopy(state.get("approval_actions", []))
        approved_ids = set(state.get("approved_action_ids", []))
        rejected_ids = set(state.get("rejected_action_ids", []))
        reflections: List[str] = []

        pending = [a for a in approval_actions if a.get("status") == "PENDING_APPROVAL"]

        if not approval_actions:
            return {
                "status": "learning",
                "reflections": ["No approval-required actions pending."],
                "logs": [self._log("approval_handler", "No pending approvals")],
            }

        # Si aún no hay respuesta del usuario y hay acciones pendientes,
        # interrumpimos el grafo para permitir la reanudación con el checkpointer.
        if pending and not approved_ids and not rejected_ids:
            interrupt(
                {
                    "type": "approval_required",
                    "message": f"{len(pending)} action(s) require user approval.",
                    "pending_action_ids": [a["action_id"] for a in pending],
                }
            )

        executed: List[Dict[str, Any]] = []
        for rec in approval_actions:
            if rec["action_id"] in approved_ids:
                rec["status"] = "APPROVED"
                executed.append(rec)
                reflections.append(f"Approved and executed {rec['action_id']}: {rec['action']}")
            elif rec["action_id"] in rejected_ids:
                rec["status"] = "REJECTED"
                reflections.append(f"Rejected {rec['action_id']}: {rec['action']}")
            else:
                rec["status"] = "PENDING_APPROVAL"

        return {
            "approval_actions": approval_actions,
            "reflections": reflections,
            "status": "learning" if not any(a["status"] == "PENDING_APPROVAL" for a in approval_actions) else "awaiting_approval",
            "logs": [self._log("approval_handler", f"Executed {len(executed)} approved action(s)")],
        }

    # --------------------------------------------------------------------------
    # Aplicar acciones aprobadas al itinerario
    # --------------------------------------------------------------------------
    def apply_approved_actions_node(self, state: AdaptiveState) -> Dict[str, Any]:
        approval_actions = copy.deepcopy(state.get("approval_actions", []))
        itinerary = copy.deepcopy(state.get("itinerary", []))
        recommendations = copy.deepcopy(state.get("recommendations", []))
        reflections: List[str] = []

        for rec in approval_actions:
            if rec.get("status") != "APPROVED":
                continue
            item = next((i for i in itinerary if i["id"] == rec["item_id"]), None)
            if item:
                item["notes"].append(f"User-approved: {rec['action']} ({rec['reason']})")
                if rec.get("cost_impact", 0.0) > 0:
                    item["cost"] = round(item.get("cost", 0.0) + rec["cost_impact"], 2)
            # Mantener sincronizado el estado de la recomendación para aprendizaje
            for r in recommendations:
                if r.get("action_id") == rec.get("action_id"):
                    r["status"] = "APPROVED"
            reflections.append(f"Applied approved action to itinerary: {rec['action']}")

        return {
            "itinerary": itinerary,
            "recommendations": recommendations,
            "reflections": reflections,
            "logs": [self._log("apply_approved", "Applied approved actions to itinerary")],
        }

    # --------------------------------------------------------------------------
    # Aprendizaje: actualizar perfil y memoria de patrones
    # --------------------------------------------------------------------------
    def learn_and_update_profile_node(self, state: AdaptiveState) -> Dict[str, Any]:
        user_id = state["request"].get("user_id", "anonymous")
        profile = self.memory.get_profile(user_id)
        reflections: List[str] = []
        beliefs: List[Dict[str, Any]] = []

        # Actualizar preferencias del perfil con las explícitas de la request
        req_prefs = state["request"].get("preferences", {})
        profile.preferences.update(req_prefs)

        for rec in state.get("recommendations", []):
            action = rec.get("action", "")
            status = rec.get("status", "PENDING_APPROVAL")
            source = rec.get("source_type", "AI_INFERENCE")
            category = rec.get("category", "general")
            pattern_key = f"{category}:{action}"

            if status == "AUTO_EXECUTED":
                # Reforzar patrón existente
                utility = 0.5
                outcome = "accepted"
                reflections.append(f"Reinforced pattern {pattern_key} from auto-execution.")
            elif status == "APPROVED":
                # Inferencia aprobada: promover a patrón
                utility = 1.0
                outcome = "accepted"
                reflections.append(f"Promoted inference {pattern_key} to pattern (user approved).")
            elif status == "REJECTED":
                utility = -1.0
                outcome = "rejected"
                reflections.append(f"User rejected {pattern_key}; penalizing pattern score.")
            else:
                continue

            profile.record_outcome(pattern_key, action, outcome, utility)
            beliefs.append(
                Belief(
                    fact=f"Recommendation '{action}' outcome={outcome}, utility={utility}",
                    certainty=1.0,
                    source="adaptive_learning",
                    topic="preference",
                ).to_dict()
            )

        # Guardar preferencias actualizadas
        self.memory.save_profile(profile)

        return {
            "status": "finalizing",
            "profile": profile.to_dict(),
            "beliefs": beliefs,
            "reflections": reflections,
            "logs": [self._log("learn_and_update_profile", "Profile and pattern memory updated")],
        }
