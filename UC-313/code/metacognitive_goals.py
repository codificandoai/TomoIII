"""Gestión segura de objetivos del self-model por metacognición (UC-296)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from memory_config import GoalConfig


@dataclass
class GoalProposal:
    proposal_id: str
    proposed_goal: str
    reason: str
    current_goal: str
    conditions_met: bool
    issues: List[str]
    trace: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "proposed_goal": self.proposed_goal,
            "reason": self.reason,
            "current_goal": self.current_goal,
            "conditions_met": self.conditions_met,
            "issues": self.issues,
            "trace": self.trace,
        }


class GoalManager:
    """Permite proponer y aplicar cambios al `current_goal` del self-model de
    forma segura, condicionada a políticas y completamente trazable.

    Políticas aplicadas:
    1. El objetivo propuesto debe coincidir con un patrón permitido.
    2. Debe existir una justificación con contexto (métricas o eventos).
    3. Si ``require_approval_for_goal_change`` es True, el cambio queda propuesto
       pero no aplicado hasta aprobación externa.
    """

    def __init__(self, config: Optional[GoalConfig] = None) -> None:
        self.config = config or GoalConfig()

    def propose_goal_change(
        self,
        current_goal: str,
        proposed_goal: str,
        reason: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> GoalProposal:
        context = context or {}
        issues: List[str] = []

        if proposed_goal not in self.config.allowed_goal_patterns:
            issues.append(
                f"Goal '{proposed_goal}' not in allowed patterns: {self.config.allowed_goal_patterns}"
            )

        if not reason or len(reason) < 10:
            issues.append("Reason must have at least 10 characters.")

        if not context.get("metrics") and not context.get("events"):
            issues.append("Goal change requires supporting metrics or events.")

        conditions_met = len(issues) == 0
        trace = {
            "current_goal": current_goal,
            "proposed_goal": proposed_goal,
            "reason": reason,
            "context": context,
            "conditions_met": conditions_met,
            "approval_required": self.config.require_approval_for_goal_change,
        }

        return GoalProposal(
            proposal_id=str(uuid.uuid4())[:8],
            proposed_goal=proposed_goal,
            reason=reason,
            current_goal=current_goal,
            conditions_met=conditions_met,
            issues=issues,
            trace=trace,
        )

    def apply_goal_change(
        self,
        current_goal: str,
        proposed_goal: str,
        reason: str,
        context: Optional[Dict[str, Any]] = None,
        approved: bool = False,
    ) -> Dict[str, Any]:
        proposal = self.propose_goal_change(current_goal, proposed_goal, reason, context)

        if not proposal.conditions_met:
            return {
                "status": "rejected",
                "proposal": proposal.to_dict(),
                "new_goal": current_goal,
            }

        if self.config.require_approval_for_goal_change and not approved:
            return {
                "status": "awaiting_approval",
                "proposal": proposal.to_dict(),
                "new_goal": current_goal,
            }

        return {
            "status": "applied",
            "proposal": proposal.to_dict(),
            "new_goal": proposed_goal,
            "trace": {
                "previous_goal": current_goal,
                "new_goal": proposed_goal,
                "applied_at": datetime.now(timezone.utc).isoformat(),
            },
        }
