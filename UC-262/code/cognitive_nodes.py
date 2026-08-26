"""Nodos cognitivos avanzados para UC-262: memoria, razonamiento, autorreflexión, colaboración y meta-aprendizaje."""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from langgraph.types import interrupt

from config import AgentConfig, AppConfig, get_config
from evolution import EvolutionEngine
from memory import LongTermMemory
from models import Belief, Desire, Intention, Reflection, TravelRequest, now_iso
from planner import default_weights
from safety import SafetyGuard
from state import GenericAIState
from world_simulator import WorldSimulator


class CognitiveNodes:
    """Nodos del copiloto genérico evolutivo."""

    def __init__(
        self,
        memory: LongTermMemory,
        world: WorldSimulator,
        engine: EvolutionEngine,
        safety: SafetyGuard,
        config: AgentConfig,
    ) -> None:
        self.memory = memory
        self.world = world
        self.engine = engine
        self.safety = safety
        self.config = config

    def _log(self, node: str, message: str, item_id: str = "") -> Dict[str, Any]:
        return {"node": node, "item_id": item_id, "message": message, "timestamp": now_iso()}

    def _reflection(self, stage: str, message: str) -> Dict[str, Any]:
        return Reflection(stage=stage, message=message).to_dict()

    # --------------------------------------------------------------------------
    # 1. Entrada y memoria
    # --------------------------------------------------------------------------
    def input_and_memory_node(self, state: GenericAIState) -> Dict[str, Any]:
        request = TravelRequest.from_dict(state["request"])
        text = " ".join([request.origin, request.destination, str(request.preferences)])
        check = self.safety.check_input(text)
        flags = check["flags"]
        missing: List[str] = []

        for field in ("origin", "destination", "departure_date"):
            if not getattr(request, field):
                missing.append(f"{field} is required")

        if missing or not check["allowed"]:
            return {
                "status": "awaiting_input",
                "missing_info": missing or ["Security check failed"],
                "safety_flags": flags,
                "reflections": [self._reflection("input", f"Input validation failed: {missing or flags}")],
                "logs": [self._log("input", "Validation failed")],
            }

        profile = self.memory.get_profile(request.user_id)
        memory_context = {
            "user_id": profile.user_id,
            "preferences": profile.preferences,
            "long_term_goals": profile.long_term_goals,
            "learned_rules": [r["rule"] for r in profile.learned_rules],
            "past_mistakes": profile.past_mistakes,
            "policy_archive_count": len(profile.policy_archive),
        }

        # Creencias iniciales derivadas de la memoria
        beliefs: List[Dict[str, Any]] = []
        for rule in memory_context["learned_rules"]:
            beliefs.append(
                Belief(fact=f"Learned rule: {rule}", certainty=0.9, source="long_term_memory", topic="rule").to_dict()
            )
        for goal in memory_context["long_term_goals"]:
            beliefs.append(
                Belief(fact=f"Long-term goal: {goal}", certainty=0.9, source="long_term_memory", topic="goal").to_dict()
            )

        desires = [
            Desire(goal="Maximize plan quality for user", priority=9),
            Desire(goal="Respect learned rules and constraints", priority=8),
            Desire(goal="Minimize cost within budget", priority=7 if request.budget else 4),
            Desire(goal="Align with long-term goals", priority=6),
        ]

        return {
            "status": "evolving",
            "memory_context": memory_context,
            "beliefs": beliefs,
            "desires": [d.to_dict() for d in desires],
            "reflections": [
                self._reflection("memory", f"Loaded profile for {request.user_id} with {len(beliefs)} beliefs.")
            ],
            "logs": [self._log("memory", f"Loaded profile {request.user_id}")],
        }

    # --------------------------------------------------------------------------
    # 2. Evolución de agentes
    # --------------------------------------------------------------------------
    def evolution_node(self, state: GenericAIState) -> Dict[str, Any]:
        request = TravelRequest.from_dict(state["request"])
        memory_rules = state.get("memory_context", {}).get("learned_rules", [])
        candidates, stats = self.engine.evolve(request, memory_rules)

        reasoning: List[str] = []
        reasoning.append(
            f"Evolved {len(candidates)} agents across {stats['generations']} generations. "
            f"Best fitness={stats['history'][-1]['best_fitness']:.4f}."
        )

        best_candidate = candidates[0] if candidates else None
        return {
            "status": "reflecting",
            "population": [c.to_dict() for c in candidates],
            "generation": stats["generations"],
            "best_candidate": best_candidate.to_dict() if best_candidate else None,
            "evolution_stats": stats,
            "reasoning_chain": state.get("reasoning_chain", []) + reasoning,
            "reflections": [self._reflection("evolve", reasoning[-1])],
            "logs": [self._log("evolve", f"Evolution completed with {len(candidates)} candidates")],
            "audit_trail": [
                {
                    "stage": "evolution",
                    "best_agent_id": best_candidate.agent_id if best_candidate else None,
                    "fitness": best_candidate.evaluation.get("fitness") if best_candidate else None,
                    "timestamp": now_iso(),
                }
            ],
        }

    # --------------------------------------------------------------------------
    # 3. Razonamiento
    # --------------------------------------------------------------------------
    def reasoning_node(self, state: GenericAIState) -> Dict[str, Any]:
        best = state.get("best_candidate") or {}
        plan = best.get("plan", [])
        genome = best.get("genome", {})
        weights = genome.get("weights", default_weights())

        reasoning: List[str] = []
        reasoning.append("Reasoning about the evolved best candidate:")
        reasoning.append(f"- Genome weights: {weights}")
        total_cost = sum(i.get("cost", 0.0) for i in plan)
        reasoning.append(f"- Estimated total cost: {total_cost:.2f}")
        for item in plan:
            reasoning.append(
                f"- {item['item_type']} {item['id']}: {item['action']} (cost={item['cost']})"
            )

        intentions = [
            Intention(
                plan_name="Execute best evolved plan",
                action="execute_plan",
                target_desire="Maximize plan quality for user",
                reasoning=f"Best candidate {best.get('agent_id')} achieved fitness {best.get('evaluation', {}).get('fitness')}",
            ).to_dict()
        ]

        return {
            "status": "reflecting",
            "reasoning_chain": state.get("reasoning_chain", []) + reasoning,
            "intentions": intentions,
            "reflections": [self._reflection("reason", "Generated explicit reasoning chain for the best plan.")],
            "logs": [self._log("reason", f"Reasoning over best candidate {best.get('agent_id')}")],
        }

    # --------------------------------------------------------------------------
    # 4. Autorreflexión
    # --------------------------------------------------------------------------
    def self_reflection_node(self, state: GenericAIState) -> Dict[str, Any]:
        best = state.get("best_candidate") or {}
        plan = best.get("plan", [])
        memory_rules = state.get("memory_context", {}).get("learned_rules", [])
        long_term_goals = state.get("memory_context", {}).get("long_term_goals", [])
        request = TravelRequest.from_dict(state["request"])

        critique_parts: List[str] = []
        contradictions: List[str] = []

        # Detectar violaciones a reglas de memoria
        for item in plan:
            if item.get("item_type") == "flight":
                details = item.get("details", {})
                for rule in memory_rules:
                    if "escala" in rule.lower() and "menores a 90" in rule.lower():
                        if not details.get("direct") and details.get("duration_minutes", 120) < 90:
                            contradictions.append(
                                f"Plan violates learned rule '{rule}' on flight {item['id']}."
                            )

        # Verificar alineación con objetivos de largo plazo
        if long_term_goals:
            goals_text = " ".join(long_term_goals).lower()
            if "platino" in goals_text or "status" in goals_text:
                pref_airline = (request.preferences or {}).get("airline")
                if pref_airline and not any(
                    i.get("details", {}).get("airline") == pref_airline
                    for i in plan if i.get("item_type") == "flight"
                ):
                    contradictions.append(
                        f"Plan does not include preferred airline {pref_airline}, conflicting with long-term goal."
                    )

        # Presupuesto
        total_cost = sum(i.get("cost", 0.0) for i in plan)
        if request.budget is not None and total_cost > request.budget:
            contradictions.append(
                f"Plan cost {total_cost:.2f} exceeds budget {request.budget:.2f}."
            )

        if contradictions:
            critique_parts.append(
                "CRITICAL: The evolved best plan contradicts long-term memory/rules: "
                + "; ".join(contradictions)
            )
        else:
            critique_parts.append("The plan aligns with memory, rules and long-term goals.")

        critique = " ".join(critique_parts)

        return {
            "status": "collaborating" if contradictions else "executing",
            "self_critique": critique,
            "reflections": [self._reflection("self_reflect", critique)],
            "logs": [self._log("self_reflect", f"Critique: {critique[:120]}")],
            "audit_trail": [
                {
                    "stage": "self_reflection",
                    "has_contradictions": bool(contradictions),
                    "contradictions": contradictions,
                    "timestamp": now_iso(),
                }
            ],
        }

    # --------------------------------------------------------------------------
    # 5. Colaboración (interrupción)
    # --------------------------------------------------------------------------
    def collaboration_node(self, state: GenericAIState) -> Dict[str, Any]:
        request = TravelRequest.from_dict(state["request"])
        feedback = request.human_feedback or state.get("human_feedback", "")
        approved = request.approved_alternative or state.get("approved_alternative", "")

        # Si hay feedback previo, continuar sin interrumpir
        if feedback or approved:
            return {
                "status": "executing",
                "reflections": [
                    self._reflection("collaborate", f"Resuming with human feedback: {feedback or approved}")
                ],
                "logs": [self._log("collaborate", "Human feedback received, resuming")],
            }

        critique = state.get("self_critique", "")
        best = state.get("best_candidate") or {}
        alternatives = self._generate_alternatives(request, best)

        interrupt_payload = {
            "type": "collaboration_required",
            "message": (
                "El sistema detectó una contradicción entre el plan evolucionado y la memoria a largo plazo. "
                "Necesito tu opinión antes de continuar."
            ),
            "critique": critique,
            "reasoning_chain": state.get("reasoning_chain", []),
            "best_plan": best.get("plan", []),
            "alternatives": alternatives,
            "resume_endpoint": "/api/v1/generic/resume",
        }
        interrupt(interrupt_payload)
        # El nodo no retorna normalmente; LangGraph pausa el grafo.
        return {}

    def _generate_alternatives(
        self,
        request: TravelRequest,
        best: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Genera alternativas simples para presentar al usuario."""
        alternatives: List[Dict[str, Any]] = []
        alternatives.append(
            {
                "alternative_id": "alt-1",
                "description": "Usar el plan evolucionado actual (puede requerir excepción).",
                "action": "accept_best",
            }
        )
        alternatives.append(
            {
                "alternative_id": "alt-2",
                "description": "Aumentar el presupuesto o relajar una regla aprendida.",
                "action": "relax_constraint",
            }
        )
        alternatives.append(
        {
                "alternative_id": "alt-3",
                "description": "Re-evolucionar con pesos más conservadores (menor riesgo).",
                "action": "re_evolve_safe",
            }
        )
        return alternatives

    # --------------------------------------------------------------------------
    # 6. Ejecución y reserva
    # --------------------------------------------------------------------------
    def execute_node(self, state: GenericAIState) -> Dict[str, Any]:
        request = TravelRequest.from_dict(state["request"])
        best = state.get("best_candidate") or {}
        plan = copy.deepcopy(best.get("plan", []))
        reflections: List[Dict[str, Any]] = []
        logs: List[Dict[str, Any]] = []
        safety_flags: List[str] = []

        if not request.confirm_irreversible:
            return {
                "status": "awaiting_confirmation",
                "requires_confirmation": True,
                "itinerary": plan,
                "reflections": [self._reflection("execute", "Plan requires user confirmation before booking.")],
                "logs": [self._log("execute", "Awaiting confirmation")],
                "safety_flags": ["requires_confirmation"],
            }

        for item in plan:
            if item.get("status") != "PENDING":
                continue
            if item["item_type"] == "flight":
                result = self.world.book_flight(item["id"])
            elif item["item_type"] == "hotel":
                result = self.world.book_hotel(item["id"])
            else:
                item["status"] = "BOOKED"
                continue

            if result.get("status") == "BOOKED":
                item["status"] = "BOOKED"
                item["confirmation"] = result["confirmation"]
                reflections.append(self._reflection("execute", f"Booked {item['id']}"))
                logs.append(self._log("execute", f"Booked {item['id']}", item["id"]))
            else:
                item["status"] = "FAILED"
                reflections.append(self._reflection("execute", f"Failed to book {item['id']}: {result.get('error')}"))
                logs.append(self._log("execute", f"Failed {item['id']}: {result.get('error')}", item["id"]))

        return {
            "status": "learning",
            "itinerary": plan,
            "final_plan": plan,
            "reflections": reflections,
            "logs": logs,
            "safety_flags": safety_flags,
        }

    # --------------------------------------------------------------------------
    # 7. Meta-aprendizaje
    # --------------------------------------------------------------------------
    def meta_learning_node(self, state: GenericAIState) -> Dict[str, Any]:
        request = TravelRequest.from_dict(state["request"])
        profile = self.memory.get_profile(request.user_id)
        best = state.get("best_candidate") or {}
        plan = state.get("final_plan", [])
        feedback = request.human_feedback or state.get("human_feedback", "")
        approved = request.approved_alternative or state.get("approved_alternative", "")
        reflections: List[Dict[str, Any]] = []

        if not plan:
            return {
                "status": "done",
                "reflections": [self._reflection("learn", "No final plan to learn from.")],
                "logs": [self._log("learn", "No plan")],
            }

        total_cost = sum(i.get("cost", 0.0) for i in plan)
        budget_ok = request.budget is None or total_cost <= request.budget

        # Actualizar reglas heurísticas a partir del feedback o resultado
        if feedback:
            if "seguro" in feedback.lower() or "safe" in feedback.lower():
                profile.add_rule(
                    "User prefers safer options even if less convenient.",
                    source="human_feedback",
                    utility=1.0,
                )
            if "temprano" in feedback.lower() or "early" in feedback.lower():
                profile.add_rule(
                    "User is willing to depart earlier to reduce risk.",
                    source="human_feedback",
                    utility=1.0,
                )

        if approved == "re_evolve_safe":
            profile.add_rule(
                "When contradictions arise, prefer re-evolving with conservative weights.",
                source="collaboration",
                utility=0.8,
            )

        if not budget_ok:
            profile.add_past_mistake(
                f"Plan for {request.origin}->{request.destination} exceeded budget ({total_cost:.2f})."
            )

        # Archivar el mejor genoma si tuvo buen fitness
        fitness = best.get("evaluation", {}).get("fitness", 0.0)
        if fitness >= 0.6:
            profile.archive_policy(best.get("genome", {}), fitness)

        self.memory.save_profile(profile)

        reflections.append(
            self._reflection(
                "learn",
                f"Updated profile for {request.user_id}: {len(profile.learned_rules)} rules, "
                f"{len(profile.policy_archive)} archived policies.",
            )
        )

        return {
            "status": "done",
            "reflections": reflections,
            "logs": [self._log("learn", f"Profile updated for {request.user_id}")],
        }

    # --------------------------------------------------------------------------
    # Finalizador
    # --------------------------------------------------------------------------
    def finalize(self, state: GenericAIState) -> Dict[str, Any]:
        best = state.get("best_candidate") or {}
        plan = state.get("final_plan", best.get("plan", []))
        total_cost = round(sum(i.get("cost", 0.0) for i in plan), 2)
        status = state.get("status", "done")
        if status not in ("done", "awaiting_input", "awaiting_confirmation", "awaiting_collaboration"):
            status = "done"

        output = {
            "request_id": state["request"].get("request_id"),
            "user_id": state["request"].get("user_id", "anonymous"),
            "thread_id": state.get("thread_id", ""),
            "status": status,
            "itinerary": plan,
            "total_cost": total_cost,
            "currency": state["request"].get("currency", "USD"),
            "best_candidate": best,
            "evolution_stats": state.get("evolution_stats", {}),
            "memory_context": state.get("memory_context", {}),
            "reasoning_chain": state.get("reasoning_chain", []),
            "self_critique": state.get("self_critique", ""),
            "reflections": state.get("reflections", []),
            "beliefs": state.get("beliefs", []),
            "desires": state.get("desires", []),
            "intentions": state.get("intentions", []),
            "audit_trail": state.get("audit_trail", []),
            "safety_flags": state.get("safety_flags", []),
            "missing_info": state.get("missing_info", []),
            "requires_confirmation": state.get("requires_confirmation", False),
        }
        return {"status": status, "final_output": output}
