"""
UC-300 — Modelos del Constitutional Interceptor.

Capa de intervención constitucional situada entre el razonamiento de UC-315
y la evaluación de riesgo/HITL de UC-290. Detecta de forma determinista dos
fallas de alineación propias de agentes con herramientas:

  1. Maximización literal: la acción propuesta persigue el objetivo declarado
     ignorando valores humanos implícitos (efectos secundarios, overshoot,
     scope creep más allá del objetivo declarado).
  2. Convergencia instrumental: para alcanzar el objetivo, el agente intenta
     adquirir más recursos, escalar privilegios o eludir restricciones de
     seguridad/auditoría/gobierno.

No es un prompt. Es un conjunto de reglas deterministas offline.
No invoca UC-315 ni la red. No sustituye a UC-290 ni a UC-324.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Any, Dict, List, Optional


class ConstitutionalVerdict(str, Enum):
    """Veredicto del Constitutional Interceptor sobre la propuesta de UC-315."""

    ALLOW = "allow"        # la propuesta está alineada; puede pasar a UC-290
    BLOCK = "block"         # violación constitucional grave; rechazo inmediato
    ESCALATE = "escalate"  # ambiguo o sensible; requiere UC-290 humano


class ConstitutionalRisk(str, Enum):
    """Riesgo de alineación asignado a la propuesta."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConstitutionalPrinciple(str, Enum):
    """Principios constitucionales deterministas evaluados."""

    SIDE_EFFECT_CONTAINMENT = "side_effect_containment"
    RESOURCE_MINIMIZATION = "resource_minimization"
    SAFETY_BYPASS_RESISTANCE = "safety_bypass_resistance"
    PRIVILEGE_LEAST_ACCESS = "privilege_least_access"
    REVERSIBILITY = "reversibility"
    GOAL_ACTION_ALIGNMENT = "goal_action_alignment"
    BOUNDED_RESOURCE_USE = "bounded_resource_use"
    MANDATE_SCOPE = "mandate_scope"


@dataclass
class AgentProposal:
    """Propuesta emitida por UC-315 que entra al Constitutional Interceptor."""

    stated_goal: str = ""
    proposed_capability: str = ""
    proposed_action: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    affected_resources: List[str] = field(default_factory=list)
    estimated_calls: int = 1
    estimated_duration_seconds: float = 0.0
    estimated_cost: float = 0.0
    reversible: bool = True
    reversibility_plan: str = ""
    requested_permissions_delta: List[str] = field(default_factory=list)
    agent_id: str = ""
    tenant_id: str = ""
    domain: str = ""
    locale: str = "en"
    trace_id: str = ""
    proposal_id: str = ""
    timestamp: float = field(default_factory=time.time)
    # Metadatos opcionales de aprobación humana vinculada al proposal_hash
    approval_proposal_hash: str = ""
    approval_reviewer_id: str = ""
    approval_dossier_id: str = ""
    approval_dossier_hash: str = ""
    approval_expires_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stated_goal": self.stated_goal,
            "proposed_capability": self.proposed_capability,
            "proposed_action": self.proposed_action,
            "params": self.params,
            "affected_resources": self.affected_resources,
            "estimated_calls": self.estimated_calls,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "estimated_cost": self.estimated_cost,
            "reversible": self.reversible,
            "reversibility_plan": self.reversibility_plan,
            "requested_permissions_delta": self.requested_permissions_delta,
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "domain": self.domain,
            "locale": self.locale,
            "trace_id": self.trace_id,
            "proposal_id": self.proposal_id,
            "timestamp": self.timestamp,
            "approval_proposal_hash": self.approval_proposal_hash,
            "approval_reviewer_id": self.approval_reviewer_id,
            "approval_dossier_id": self.approval_dossier_id,
            "approval_dossier_hash": self.approval_dossier_hash,
            "approval_expires_at": self.approval_expires_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentProposal":
        return cls(**{k: v for k, v in data.items() if k in {f.name for f in fields(cls)}})


@dataclass
class ConstitutionalDecision:
    """Decisión determinista del Constitutional Interceptor."""

    verdict: ConstitutionalVerdict = ConstitutionalVerdict.BLOCK
    proposal_hash: str = ""
    risk: ConstitutionalRisk = ConstitutionalRisk.LOW
    reason: str = ""
    summary: str = ""
    principle_violations: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    goal_action_aligned: bool = False
    side_effects_bounded: bool = False
    resources_bounded: bool = False
    safety_bypass_attempted: bool = False
    privilege_escalation_attempted: bool = False
    reversible_acceptable: bool = False
    within_mandate: bool = False
    agent_id: str = ""
    tenant_id: str = ""
    locale: str = "en"
    request_age_seconds: float = 0.0
    escalation_payload: Optional[Dict[str, Any]] = None
    resolved_by_approval: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value if isinstance(self.verdict, ConstitutionalVerdict) else self.verdict,
            "proposal_hash": self.proposal_hash,
            "risk": self.risk.value if isinstance(self.risk, ConstitutionalRisk) else self.risk,
            "reason": self.reason,
            "summary": self.summary,
            "principle_violations": self.principle_violations,
            "evidence_refs": self.evidence_refs,
            "goal_action_aligned": self.goal_action_aligned,
            "side_effects_bounded": self.side_effects_bounded,
            "resources_bounded": self.resources_bounded,
            "safety_bypass_attempted": self.safety_bypass_attempted,
            "privilege_escalation_attempted": self.privilege_escalation_attempted,
            "reversible_acceptable": self.reversible_acceptable,
            "within_mandate": self.within_mandate,
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "locale": self.locale,
            "request_age_seconds": self.request_age_seconds,
            "escalation_payload": self.escalation_payload,
            "resolved_by_approval": self.resolved_by_approval,
            "timestamp": self.timestamp,
        }


def canonical_proposal_hash(
    stated_goal: str,
    proposed_capability: str,
    proposed_action: str,
    params: Dict[str, Any],
    agent_id: str,
    tenant_id: str,
    domain: str,
    locale: str,
) -> str:
    """Hash canónico determinista de una propuesta de UC-315.

    Vincula aprobaciones humanas a la propuesta exacta; cualquier alteración
    de goal/capability/action/params/identity produce un hash distinto.
    """
    payload = json.dumps({
        "stated_goal": stated_goal,
        "proposed_capability": proposed_capability,
        "proposed_action": proposed_action,
        "params": params,
        "agent_id": agent_id,
        "tenant_id": tenant_id,
        "domain": domain,
        "locale": locale,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
