"""UC-300 — Control de separación de poderes.

Ningún agente individual puede tener al mismo tiempo las cuatro capacidades:
- proponer (propose)
- autorizar (authorize)
- ejecutar (execute)
- reescribir controles (rewrite_controls)

Este módulo implementa un registro de roles, un clasificador de acciones
y un validador deny-by-default.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class Power(str, Enum):
    """Capacidades que deben separarse entre agentes."""
    PROPOSE = "propose"
    AUTHORIZE = "authorize"
    EXECUTE = "execute"
    REWRITE_CONTROLS = "rewrite_controls"


@dataclass
class AgentPowers:
    """Poderes asignados a un agente."""
    agent_id: str
    powers: Set[Power] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "powers": sorted([p.value for p in self.powers]),
        }


class SeparationOfPowersRegistry:
    """Registro de poderes por agente."""

    def __init__(self):
        self._agents: Dict[str, AgentPowers] = {}

    def register(self, agent_id: str, powers: List[Power]) -> None:
        if agent_id not in self._agents:
            self._agents[agent_id] = AgentPowers(agent_id=agent_id)
        for p in powers:
            self._agents[agent_id].powers.add(p)

    def has_power(self, agent_id: str, power: Power) -> bool:
        return power in self._agents.get(agent_id, AgentPowers(agent_id=agent_id)).powers

    def check_conflict(self, agent_id: str, requested_action: str) -> Optional[str]:
        """Valida que el agente no abuse de poderes acumulados."""
        agent = self._agents.get(agent_id)
        if not agent:
            return None

        # Si un agente intenta ejecutar y también tiene autorización o reescritura
        if requested_action == "execute" and {Power.AUTHORIZE, Power.REWRITE_CONTROLS} & agent.powers:
            return f"agent {agent_id} cannot execute while holding authorize/rewrite_controls"

        # Si un agente intenta autorizar y también propone o ejecuta
        if requested_action == "authorize" and {Power.PROPOSE, Power.EXECUTE} & agent.powers:
            return f"agent {agent_id} cannot authorize while holding propose/execute"

        # Si un agente intenta modificar controles, no debe poder ejecutarlos
        if requested_action == "rewrite_controls" and {Power.EXECUTE, Power.AUTHORIZE} & agent.powers:
            return f"agent {agent_id} cannot rewrite controls while holding execute/authorize"

        # Prohibición absoluta: las cuatro capacidades en un mismo agente
        if agent.powers.issuperset(set(Power)):
            return f"agent {agent_id} holds all four powers: propose, authorize, execute, rewrite_controls"

        return None

    def to_dict(self) -> Dict[str, Any]:
        return {aid: ap.to_dict() for aid, ap in self._agents.items()}


class ActionPowerClassifier:
    """Clasifica acciones de herramientas en poderes separados."""

    PROPOSE_ACTIONS = {"propose", "suggest", "recommend", "decide", "advise"}
    AUTHORIZE_ACTIONS = {"authorize", "approve", "endorse", "certify"}
    REWRITE_CONTROLS_ACTIONS = {
        "add_rule", "remove_rule", "modify_policy", "set_policy", "delete_policy",
        "set_scope", "allow_environment", "deny_environment", "issue_credential",
        "revoke_credential", "rotate_secret", "change_prompt", "modify_prompt",
        "delete_prompt", "change_skill", "modify_skill", "delete_skill",
        "change_model", "modify_model", "delete_model", "grant", "revoke",
    }
    EXECUTE_PREFIX_DENY = {"modify_", "delete_", "update_", "create_", "write_", "add_"}
    # Acciones explícitas de lectura/ejecución que son seguras aunque tengan preficies anteriores
    READ_EXECUTE_ACTIONS = {"read_file", "get_price", "get_status", "send_payment"}

    @classmethod
    def classify(cls, action: str) -> Power:
        if not action:
            return Power.EXECUTE
        a = action.lower().strip()
        if a in cls.PROPOSE_ACTIONS:
            return Power.PROPOSE
        if a in cls.AUTHORIZE_ACTIONS:
            return Power.AUTHORIZE
        if a in cls.REWRITE_CONTROLS_ACTIONS:
            return Power.REWRITE_CONTROLS
        if a in cls.READ_EXECUTE_ACTIONS:
            return Power.EXECUTE
        for prefix in cls.EXECUTE_PREFIX_DENY:
            if a.startswith(prefix):
                return Power.REWRITE_CONTROLS
        return Power.EXECUTE
