"""UC-324 — Integración nativa con agent_sre de Microsoft AGT.

Envuelve `agent_runtime.KillSwitch`, `agent_sre.SLO`, `SLI` y `ErrorBudget`
para ofrecer:

- Kill switch nativo AGT con registro durable de kills.
- SLOs por skill (tasa de éxito) con presupuesto de error.
- Estado de salud por skill (healthy / warning / critical / exhausted).

Si `agent_sre` no está disponible, el manager usa una implementación
interna equivalente.
"""
from __future__ import annotations

import time
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

warnings.filterwarnings("ignore", category=DeprecationWarning)

AGT_SRE_AVAILABLE = False
AGT_SRE_ERROR: Optional[str] = None

try:
    from agent_runtime import KillSwitch
    from agent_sre import SLI, SLO, ErrorBudget

    AGT_SRE_AVAILABLE = True
except Exception as exc:  # pragma: no cover
    AGT_SRE_ERROR = str(exc)

if AGT_SRE_AVAILABLE:
    from agent_sre.slo.indicators import TimeWindow
else:
    class TimeWindow:  # type: ignore
        HOUR_1 = "HOUR_1"


class _SuccessRateSLI(SLI if AGT_SRE_AVAILABLE else object):  # type: ignore
    """SLI que registra 1.0 para éxito y 0.0 para fallo."""

    def __init__(self, name: str = "success_rate", target: float = 0.95, window: Any = TimeWindow.HOUR_1) -> None:
        if AGT_SRE_AVAILABLE:
            super().__init__(name=name, target=target, window=window)
        else:
            self.name = name
            self.target = target
            self._records: List[Dict[str, Any]] = []

    def collect(self) -> Any:
        return self.record(1.0)

    def current_value(self) -> Optional[float]:
        if AGT_SRE_AVAILABLE:
            return super().current_value()  # type: ignore
        if not self._records:
            return None
        cutoff = time.time() - 3600
        recent = [r["value"] for r in self._records if r["ts"] >= cutoff]
        if not recent:
            return None
        return sum(recent) / len(recent)

    def record(self, value: float, metadata: Optional[Dict[str, Any]] = None) -> Any:
        if AGT_SRE_AVAILABLE:
            return super().record(value, metadata)  # type: ignore
        self._records.append({"value": value, "ts": time.time(), "meta": metadata or {}})
        return None


@dataclass
class SRECheckResult:
    allowed: bool = True
    killed: bool = False
    status: str = "unknown"
    issues: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "killed": self.killed,
            "status": self.status,
            "issues": self.issues,
            "details": self.details,
        }


class AGTSREManager:
    """Gestor de SLOs y kill switch usando AGT nativo (con fallback interno)."""

    def __init__(self, agent_id: str = "uc324_orchestrator") -> None:
        self._agent_id = agent_id
        self._killed = False
        self._kill_reasons: List[str] = []
        self._slos: Dict[str, Any] = {}
        self._records: Dict[str, List[Dict[str, Any]]] = {}

        if AGT_SRE_AVAILABLE:
            self._kill_switch = KillSwitch()
            self._kill_switch.register_agent(agent_id, self._on_kill_callback)
            self._init_native_slos()
        else:
            self._kill_switch = None
            self._init_fallback_slos()

    def _init_native_slos(self) -> None:
        for skill in ["PaymentSkill", "MarketExecutionSkill", "ChangeCancelSkill"]:
            sli = _SuccessRateSLI(name="success_rate", target=0.95, window=TimeWindow.HOUR_1)
            budget = ErrorBudget(total=3.0)
            self._slos[skill] = SLO(
                name=f"{skill}_reliability",
                indicators=[sli],
                error_budget=budget,
                agent_id=self._agent_id,
            )

    def _init_fallback_slos(self) -> None:
        for skill in ["PaymentSkill", "MarketExecutionSkill", "ChangeCancelSkill"]:
            self._records[skill] = []

    def _on_kill_callback(self) -> None:
        self._killed = True

    def kill(self, reason: str = "MANUAL") -> None:
        self._killed = True
        self._kill_reasons.append(reason)
        if self._kill_switch is not None:
            try:
                from hypervisor.security.kill_switch import KillReason

                self._kill_switch.kill(
                    agent_did=self._agent_id,
                    session_id="uc324_session",
                    reason=KillReason.MANUAL,
                    details=reason,
                )
            except Exception as exc:
                self._kill_reasons.append(f"native_error: {exc}")

    def unkill(self) -> None:
        self._killed = False

    def is_killed(self) -> bool:
        return self._killed

    def kill_history(self) -> List[str]:
        return list(self._kill_reasons)

    def record(self, skill_name: str, success: bool) -> None:
        """Registra un resultado (éxito o fallo) contra el SLO de la skill."""
        if AGT_SRE_AVAILABLE and skill_name in self._slos:
            slo = self._slos[skill_name]
            for sli in slo.indicators:
                if sli.name == "success_rate":
                    sli.record(1.0 if success else 0.0, metadata={"skill": skill_name})
            if not success:
                slo.error_budget.record_event(good=False)
        else:
            self._records.setdefault(skill_name, [])
            self._records[skill_name].append(
                {"value": 1.0 if success else 0.0, "ts": time.time()}
            )

    def check(self, skill_name: str) -> SRECheckResult:
        """Verifica si el kill switch está activo o el SLO de la skill está agotado."""
        result = SRECheckResult()

        if self.is_killed():
            result.allowed = False
            result.killed = True
            result.status = "killed"
            result.issues.append("AGT SRE kill switch activo")
            return result

        if AGT_SRE_AVAILABLE and skill_name in self._slos:
            slo = self._slos[skill_name]
            status = slo.evaluate()
            result.status = status.name if hasattr(status, "name") else str(status)
            result.details = {
                "error_budget_remaining": slo.error_budget.remaining_percent,
                "error_budget_total": slo.error_budget.total,
                "error_budget_consumed": slo.error_budget.consumed,
            }
            if status.name in ("EXHAUSTED", "CRITICAL"):
                result.allowed = False
                result.issues.append(
                    f"AGT SLO '{slo.name}' está en estado {status.name}; se bloquea la ejecución"
                )
        else:
            recent = [
                r for r in self._records.get(skill_name, [])
                if r["ts"] >= time.time() - 3600
            ]
            if recent:
                rate = sum(r["value"] for r in recent) / len(recent)
                failures = len(recent) - sum(1 for r in recent if r["value"])
                result.details = {"recent_success_rate": rate, "recent_failures": failures}
                if failures >= 3 or rate < 0.5:
                    result.allowed = False
                    result.status = "critical"
                    result.issues.append(
                        f"Fallback SLO: {skill_name} tiene {failures} fallos recientes"
                    )
                elif failures >= 1:
                    result.status = "warning"
                else:
                    result.status = "healthy"
            else:
                result.status = "unknown"

        return result

    def status(self) -> Dict[str, Any]:
        """Devuelve el estado completo de SLOs y kill switch."""
        out: Dict[str, Any] = {
            "killed": self.is_killed(),
            "kill_history": self.kill_history(),
            "slos": {},
        }
        if AGT_SRE_AVAILABLE:
            for skill, slo in self._slos.items():
                status = slo.evaluate()
                out["slos"][skill] = {
                    "status": status.name if hasattr(status, "name") else str(status),
                    "error_budget_remaining": slo.error_budget.remaining_percent,
                    "error_budget_consumed": slo.error_budget.consumed,
                    "error_budget_total": slo.error_budget.total,
                }
        else:
            for skill, records in self._records.items():
                recent = [r for r in records if r["ts"] >= time.time() - 3600]
                rate = sum(r["value"] for r in recent) / len(recent) if recent else None
                out["slos"][skill] = {
                    "status": "fallback",
                    "recent_success_rate": rate,
                }
        return out
