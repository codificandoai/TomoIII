"""
UC-330 — Safety Governor para Exploitation–Exploration Governance.

Garantiza que:
- La exploración solo ocurra en entornos sandbox/simulación.
- Las acciones de producción sean explotación de acciones probadas y
  autorizadas por UC-324.
- Se registren todos los eventos de exploración para auditoría.
"""

from typing import Dict, List, Any, Optional
import time

from balance_ex_models import DecisionMode


class SafetyGovernor:
    """
    Control de seguridad para exploración-explotación.

    Reglas de oro:
    1. EXPLORAR → sandbox.
    2. EXPLOTAR → requiere autorización si es producción.
    3. RIESGO SISTÉMICO → escalar.
    """

    def __init__(self):
        self._audit_log: List[Dict[str, Any]] = []

    def evaluate(
        self,
        mode: DecisionMode,
        action: str,
        risk_score: float,
        risk_threshold: float = 0.7,
        authorized_actions: Optional[List[str]] = None,
        environment: str = "production",
    ) -> DecisionMode:
        """
        Ajusta el modo propuesto según reglas de seguridad.

        Args:
            mode: modo propuesto por el policy selector.
            action: acción candidata.
            risk_score: score de riesgo (0-1).
            risk_threshold: umbral de riesgo sistémico.
            authorized_actions: lista blanca de acciones para producción.
            environment: 'production' o 'sandbox'.

        Returns:
            Modo final autorizado.
        """
        authorized_actions = authorized_actions or []
        final_mode = mode
        reason = []

        # Regla 1: exploración nunca en producción
        if mode == DecisionMode.SANDBOX and environment == "production":
            final_mode = DecisionMode.EXPLOIT
            reason.append("exploration_forbidden_in_production")

        # Regla 2: alto riesgo → escalar
        if risk_score > risk_threshold:
            final_mode = DecisionMode.ESCALATE
            reason.append("risk_above_threshold")

        # Regla 3: acción no autorizada en producción
        if environment == "production" and action not in authorized_actions:
            final_mode = DecisionMode.ESCALATE
            reason.append("action_not_authorized_for_production")

        self._audit_log.append({
            "timestamp": time.time(),
            "proposed_mode": mode.value,
            "final_mode": final_mode.value,
            "action": action,
            "risk_score": risk_score,
            "environment": environment,
            "reasons": reason,
        })

        return final_mode

    def is_authorized_for_production(
        self,
        action: str,
        authorized_actions: List[str],
    ) -> bool:
        return action in authorized_actions

    def get_audit_log(
        self,
        limit: int = 100,
        environment: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        logs = self._audit_log
        if environment:
            logs = [l for l in logs if l.get("environment") == environment]
        return logs[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_evaluations": len(self._audit_log),
            "exploration_blocked": sum(
                1 for l in self._audit_log if l.get("proposed_mode") == "sandbox" and l.get("final_mode") != "sandbox"
            ),
            "escalations": sum(1 for l in self._audit_log if l.get("final_mode") == "escalate"),
        }

    def reset(self) -> None:
        self._audit_log.clear()
