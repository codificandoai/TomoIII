"""UC-315 — Orquestador general con skills especializadas por dominio.

El orquestador interpreta objetivos, construye planes, selecciona skills,
gestiona el estado de ejecución y coordina agentes especializados. No asume dos
arquitecturas cognitivas distintas: reutiliza el mismo patrón de orquestación y
cambia skills, modelos de mundo, fuentes de datos y reglas de autorización.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from domain_memory import DomainMemoryManager, PlanTemplate
from domain_policy import PolicyRegistry
from domain_skills import build_default_registry
from safety_supervisor_315 import SafetySupervisor315
from skill_contracts import ActionClass, SkillContract, SkillRegistry


@dataclass
class ExecutionStep:
    step_id: str
    skill_name: str
    inputs: Dict[str, Any]
    status: str = "pending"  # pending | approved | blocked | executed | failed
    safety_decision: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "skill_name": self.skill_name,
            "inputs": self.inputs,
            "status": self.status,
            "safety_decision": self.safety_decision,
            "result": self.result,
        }


@dataclass
class Plan:
    plan_id: str
    domain: str
    goal: str
    template: Optional[str]
    steps: List[ExecutionStep] = field(default_factory=list)
    status: str = "draft"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "domain": self.domain,
            "goal": self.goal,
            "template": self.template,
            "status": self.status,
            "steps": [s.to_dict() for s in self.steps],
        }


class GeneralOrchestrator:
    """Núcleo cognitivo-orquestador común parametrizado por dominio."""

    def __init__(
        self,
        skill_registry: Optional[SkillRegistry] = None,
        safety: Optional[SafetySupervisor315] = None,
    ) -> None:
        self.skills = skill_registry or build_default_registry()
        self.safety = safety or SafetySupervisor315(PolicyRegistry())
        self._memories: Dict[str, DomainMemoryManager] = {}

    def _get_memory(self, domain: str) -> DomainMemoryManager:
        if domain not in self._memories:
            self._memories[domain] = DomainMemoryManager(domain)
        return self._memories[domain]

    def build_plan(
        self,
        goal: str,
        domain: str,
        user_roles: Optional[List[str]] = None,
    ) -> Plan:
        """Construye un plan a partir de una plantilla del dominio o su equivalente semántico."""
        memory = self._get_memory(domain)
        plan_id = str(uuid.uuid4())[:8]
        plan = Plan(plan_id=plan_id, domain=domain, goal=goal, template=None)

        # Recuperación semántica de plantilla abstracta
        template = memory.retrieve_similar_template(goal)
        if template is None:
            template = memory.retrieve_template("transport_booking" if domain == "reservations" else "order_lifecycle")

        if template:
            plan.template = template.name
            # Adaptar pasos concretos a skills disponibles en este dominio
            for idx, step_desc in enumerate(template.steps, 1):
                skill = self._select_skill_for_step(step_desc, domain, goal)
                if skill:
                    inputs = self._infer_inputs(skill, goal, step_desc)
                    plan.steps.append(ExecutionStep(
                        step_id=f"{plan_id}-{idx:02d}",
                        skill_name=skill.name,
                        inputs=inputs,
                    ))
        else:
            # Fallback: intentar skill directa
            skill = self._select_skill_for_step(goal, domain, goal)
            if skill:
                plan.steps.append(ExecutionStep(
                    step_id=f"{plan_id}-01",
                    skill_name=skill.name,
                    inputs=self._infer_inputs(skill, goal, goal),
                ))

        plan.status = "draft"
        return plan

    def validate_and_execute(
        self,
        plan: Plan,
        user_roles: Optional[List[str]] = None,
        domain_state: Optional[Dict[str, Any]] = None,
        auto_approve: bool = False,
    ) -> Plan:
        """Valida cada paso con el Safety Supervisor y ejecuta si está aprobado."""
        user_roles = user_roles or ["anonymous"]
        domain_state = domain_state or {}
        for step in plan.steps:
            skill = self.skills.get(step.skill_name)
            if skill is None:
                step.status = "failed"
                step.result = {"error": f"Skill {step.skill_name} no registrada"}
                continue

            decision = self.safety.check(
                skill,
                step.inputs,
                user_roles,
                domain_state,
                require_human_approval=not auto_approve and skill.action_class in (ActionClass.EXECUTE, ActionClass.TRANSACT, ActionClass.DELETE),
            )
            step.safety_decision = decision

            if not decision["allowed"]:
                step.status = "blocked"
                self.safety.record_failure(skill.name)
                continue

            if decision["requires_approval"] and not auto_approve:
                step.status = "awaiting_approval"
                continue

            step.status = "executed"
            step.result = self._execute_skill(skill, step.inputs, plan.domain)
            if not step.result.get("success", True):
                step.status = "failed"
                self.safety.record_failure(skill.name)

        plan.status = self._aggregate_plan_status(plan)
        return plan

    # Palabras demasiado genéricas que no deberían activar el fallback
    _STOPWORDS = {
        "y", "o", "el", "la", "los", "las", "de", "del", "en", "un", "una",
        "con", "por", "para", "que", "fill", "the", "and", "or", "a", "an",
        "resultado", "result", "verificar", "verificación", "confirmar", "confirmación",
    }

    def _select_skill_for_step(self, step_desc: str, domain: str, goal: str) -> Optional[SkillContract]:
        candidates = [self.skills.get(n) for n in self._skill_names_for_step(step_desc, domain, goal)]
        # fallback: buscar por keywords significativas en el propósito de la skill
        if not any(candidates):
            words = [w for w in step_desc.lower().split() if w not in self._STOPWORDS]
            candidates = [
                s for s in self.skills._skills.values()
                if s.domain == domain and any(k in s.purpose.lower() for k in words)
            ]
        return candidates[0] if candidates and candidates[0] is not None else None

    @staticmethod
    def _skill_names_for_step(step_desc: str, domain: str, goal: str) -> List[str]:
        text = step_desc.lower()
        goal_lower = goal.lower()
        if domain == "reservations":
            # Determinar el modo de transporte desde el objetivo o el paso concreto
            transport_keywords = {
                "flight": ["vuelo", "flight", "aéreo", "aereo", "avión"],
                "rail": ["tren", "rail", "ferroviario", "ferrocarril"],
            }
            is_flight = any(k in goal_lower or k in text for k in transport_keywords["flight"])
            is_rail = any(k in goal_lower or k in text for k in transport_keywords["rail"])

            if any(k in text for k in ("vuelo", "flight", "aéreo", "aereo", "avión")):
                return ["FlightBookingSkill"]
            if any(k in text for k in ("tren", "rail", "ferroviario", "ferrocarril")):
                return ["RailBookingSkill"]

            # Pasos genéricos de reserva se enrutan al modo de transporte del objetivo
            if any(k in text for k in ("consultar", "opciones", "disponible", "buscar", "itinerario", "seleccionar", "filtrar", "ejecutar", "reserva", "reservar")):
                return ["FlightBookingSkill"] if is_flight else ["RailBookingSkill"] if is_rail else []
            if any(k in text for k in ("pago", "payment", "pag")):
                return ["PaymentSkill"]
            if any(k in text for k in ("identidad", "validar", "pasajero")):
                return ["IdentityValidationSkill"]
            if any(k in text for k in ("notificar", "confirmar", "enviar", "notificación")):
                return ["NotificationSkill"]
            if any(k in text for k in ("cancelar", "cambiar", "change", "cancel")):
                return ["ChangeCancelSkill"]
        elif domain == "trading":
            if any(k in text for k in ("mercado", "market data", "datos", "bid", "ask")):
                return ["MarketDataSkill"]
            if any(k in text for k in ("predecir", "predict", "señal", "signal")):
                return ["MarketPredictionSkill"]
            if any(k in text for k in ("riesgo", "risk", "exposición")):
                return ["FinancialRiskSkill"]
            if any(k in text for k in ("orden", "order", "ejecutar", "enviar")):
                return ["MarketExecutionSkill"]
        return []

    @staticmethod
    def _infer_inputs(skill: SkillContract, goal: str, step_desc: str) -> Dict[str, Any]:
        inputs: Dict[str, Any] = {}
        text = f"{goal} {step_desc}".lower()
        for param in skill.inputs:
            if param.name in ("origin", "destination"):
                # Heurística simple: palabra siguiente a "desde" o "hacia"
                marker = "desde" if param.name == "origin" else "hacia"
                idx = text.find(marker)
                if idx >= 0:
                    parts = text[idx + len(marker):].strip().split()
                    inputs[param.name] = parts[0].capitalize() if parts else "MAD"
                else:
                    inputs[param.name] = "MAD" if param.name == "origin" else "BCN"
            elif param.name == "date":
                inputs[param.name] = "2026-12-15"
            elif param.name == "symbol":
                inputs[param.name] = "AAPL"
            elif param.name == "side":
                inputs[param.name] = "BUY"
            elif param.name == "quantity":
                inputs[param.name] = 100
            elif param.name == "limit_price":
                inputs[param.name] = 150.0
            elif param.name == "exposure_usd":
                inputs[param.name] = 5000.0
            elif param.name == "limit_usd":
                inputs[param.name] = 100_000.0
            elif param.name == "amount":
                inputs[param.name] = 275.0
            elif param.name == "currency":
                inputs[param.name] = "USD"
            elif param.name == "payment_method":
                inputs[param.name] = "credit_card"
            elif param.name == "user_id":
                inputs[param.name] = "USR-123"
            elif param.name == "to":
                inputs[param.name] = "user@example.com"
            elif param.name == "channel":
                inputs[param.name] = "email"
            elif param.name == "message":
                inputs[param.name] = f"Confirmación: {step_desc}"
            elif param.name == "reservation_id":
                inputs[param.name] = "RES-ABC"
            elif param.name == "action":
                inputs[param.name] = "cancel"
        return inputs

    def _execute_skill(self, skill: SkillContract, inputs: Dict[str, Any], domain: str) -> Dict[str, Any]:
        if skill.executor is None:
            return {"success": False, "error": "Skill no tiene executor"}
        try:
            return {"success": True, "output": skill.executor(inputs, domain)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    def _aggregate_plan_status(plan: Plan) -> str:
        if any(s.status == "failed" for s in plan.steps):
            return "failed"
        if any(s.status == "blocked" for s in plan.steps):
            return "blocked"
        if any(s.status == "awaiting_approval" for s in plan.steps):
            return "awaiting_approval"
        if all(s.status == "executed" for s in plan.steps):
            return "completed"
        return "draft"
