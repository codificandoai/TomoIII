"""UC-315 — Contratos de habilidades (Skill Contracts).

Cada skill se registra con metadatos explícitos: esquema, permisos, coste,
latencia, pre/postcondiciones, riesgo y mecanismos de compensación. Esto
permite que el orquestador comparta un núcleo común pero mantenga skills,
memorias y políticas separadas por dominio.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionClass(str, Enum):
    READ = "read"
    PREDICT = "predict"
    ANALYZE = "analyze"
    TRANSACT = "transact"
    EXECUTE = "execute"
    DELETE = "delete"


@dataclass
class SkillParameter:
    name: str
    type: str = "string"
    description: str = ""
    required: bool = True


@dataclass
class SkillContract:
    """Descriptor explícito de una habilidad operacional."""

    name: str
    version: str = "1.0.0"
    domain: str = "generic"  # trading | reservations | generic
    purpose: str = ""
    inputs: List[SkillParameter] = field(default_factory=list)
    outputs: List[SkillParameter] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    required_roles: List[str] = field(default_factory=list)
    action_class: ActionClass = ActionClass.READ
    estimated_cost: float = 0.0
    estimated_latency_ms: float = 0.0
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    reversible: bool = True
    compensation: Optional[str] = None
    executor: Optional[Callable[[Dict[str, Any], str], Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "domain": self.domain,
            "purpose": self.purpose,
            "inputs": [{"name": p.name, "type": p.type, "description": p.description, "required": p.required} for p in self.inputs],
            "outputs": [{"name": p.name, "type": p.type, "description": p.description, "required": p.required} for p in self.outputs],
            "permissions": self.permissions,
            "required_roles": self.required_roles,
            "action_class": self.action_class.value,
            "estimated_cost": self.estimated_cost,
            "estimated_latency_ms": self.estimated_latency_ms,
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "risk_level": self.risk_level.value,
            "reversible": self.reversible,
            "compensation": self.compensation,
        }


class SkillRegistry:
    """Registro centralizado de skills con separación por dominio."""

    def __init__(self) -> None:
        self._skills: Dict[str, SkillContract] = {}

    def register(self, skill: SkillContract) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[SkillContract]:
        return self._skills.get(name)

    def list_skills(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        skills = self._skills.values()
        if domain:
            skills = [s for s in skills if s.domain == domain]
        return [s.to_dict() for s in skills]

    def domains(self) -> List[str]:
        return sorted({s.domain for s in self._skills.values()})

    def find_for_action(self, domain: str, action_class: ActionClass) -> List[SkillContract]:
        return [s for s in self._skills.values() if s.domain == domain and s.action_class == action_class]
