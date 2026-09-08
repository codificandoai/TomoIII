"""UC-324 — Protocolo de contención de Sandbox para agentes autónomos.

Integra capas de gobernanza externa, stress testing, red-teaming, verificación
post-acción, circuit breakers, frontera criptográfica, anti-inyección y evaluación
de trayectoria, sin reemplazar el `SafetySupervisor315` ni el orquestador base.

Los módulos del cerebro AGI se importan desde `UC-315/code` usando el helper
`_import_paths.py`; no se copian archivos.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import _import_paths  # noqa: F401

from domain_policy import PolicyRegistry
from external_toolkit_adapters import (
    ExternalAdapter,
    Gate,
    build_default_adapters,
)
from general_orchestrator import GeneralOrchestrator, Plan
from safety_supervisor_315 import SafetySupervisor315
from skill_contracts import SkillContract


try:
    from agt_sre_integration import AGTSREManager

    _SRE_AVAILABLE = True
except Exception:  # pragma: no cover
    _SRE_AVAILABLE = False

try:
    from safety_critical_monitor import SafetyCriticalMonitor, default_monitor_for_critical_skills

    _SCM_AVAILABLE = True
except Exception:  # pragma: no cover
    _SCM_AVAILABLE = False


class ContainmentMode(str, Enum):
    AUDIT = "audit"       # Evaluar pero no bloquear
    ENFORCE = "enforce"   # Bloquear si falla alguna capa
    DISABLED = "disabled" # No ejecutar validadores


@dataclass
class ContainmentDecision:
    plan_id: str
    step_id: str
    allowed: bool
    gate: str
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    adapters: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "step_id": self.step_id,
            "allowed": self.allowed,
            "gate": self.gate,
            "issues": self.issues,
            "warnings": self.warnings,
            "adapters": self.adapters,
            "timestamp": self.timestamp,
        }


class ContainmentSandbox:
    """Sandbox de contención que envuelve al orquestador.

    No modifica el cerebro AGI base; actúa como un *middleware* opcional que
    puede deshabilitarse por completo (`mode=disabled`) o pasar a modo
    auditoría (`audit`) para pruebas sin afectar la ejecución.
    """

    def __init__(
        self,
        orchestrator: Optional[GeneralOrchestrator] = None,
        adapters: Optional[List[ExternalAdapter]] = None,
        mode: ContainmentMode = ContainmentMode.ENFORCE,
        enable_kill_switch: bool = True,
        crypto_secret: Optional[str] = None,
        coordinator: Optional[Any] = None,
        safe_shutdown_adapters: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.orchestrator = orchestrator or GeneralOrchestrator(
            safety=SafetySupervisor315(PolicyRegistry())
        )
        self.adapters = adapters or build_default_adapters(secret=crypto_secret)
        self.mode = mode
        self._enable_kill_switch = enable_kill_switch
        self._audit_log: List[ContainmentDecision] = []
        self._failure_history: Dict[str, int] = {}
        self._sre = AGTSREManager() if _SRE_AVAILABLE else None
        self._monitor = (
            default_monitor_for_critical_skills()
            if _SCM_AVAILABLE
            else None
        )
        # UC-324 Safe Shutdown: internal raw latch and optional coordinator
        self._raw_kill_switch = False
        self._coordinator = coordinator
        self._safe_shutdown_adapters = safe_shutdown_adapters or {}
        self._shutdown_coordinator = coordinator

    # ------------------------------------------------------------------
    # Kill switch global
    # ------------------------------------------------------------------
    def _raw_kill(self) -> None:
        """Internal raw latch; does NOT coordinate shutdown."""
        if self._enable_kill_switch:
            self._raw_kill_switch = True
            if self._sre is not None:
                self._sre.kill("manual")

    def _raw_unkill(self) -> None:
        """Internal raw unlatch; only coordinator may call after approved reactivation."""
        self._raw_kill_switch = False
        if self._sre is not None:
            self._sre.unkill()

    def kill(self) -> None:
        """Public kill: set raw latch and optionally coordinate safe shutdown."""
        self._raw_kill()

    def unkill(self) -> None:
        """Public unkill: ONLY clears raw latch when safe-shutdown is not terminal.

        When the SafeShutdownCoordinator is in SAFE_STOPPED/CONTAINED, this
        method does NOT bypass human reactivation. Only a successful
        request_reactivation calls _raw_unkill internally.
        """
        # Do not bypass coordinator's human-approval gate
        if self._shutdown_coordinator_terminal():
            return
        self._raw_unkill()

    def is_killed(self) -> bool:
        if self._raw_kill_switch:
            return True
        if self._sre is not None:
            return self._sre.is_killed()
        return False

    def _shutdown_coordinator_terminal(self) -> bool:
        """True if the safe shutdown coordinator is in a terminal state."""
        coord = getattr(self, "_shutdown_coordinator", None)
        if coord is None:
            return False
        from safe_shutdown_models import ShutdownState
        return coord.state in (ShutdownState.SAFE_STOPPED, ShutdownState.CONTAINED)

    # ------------------------------------------------------------------
    # Circuit breaker / safety-critical monitor
    # ------------------------------------------------------------------
    def trip_circuit_breaker(self, skill_name: str) -> None:
        if self._monitor is not None:
            self._monitor.manual_trip(skill_name)

    def reset_circuit_breaker(self, skill_name: str) -> None:
        if self._monitor is not None:
            self._monitor.manual_reset(skill_name)

    def monitor_status(self) -> Dict[str, Any]:
        if self._monitor is not None:
            return self._monitor.status()
        return {"breakers": {}, "metrics": {}}

    # ------------------------------------------------------------------
    # Validación por gate
    # ------------------------------------------------------------------
    def _run_gate(
        self,
        gate: Gate,
        context: Dict[str, Any],
    ) -> ContainmentDecision:
        plan_id = context.get("plan_id", str(uuid.uuid4())[:8])
        step_id = context.get("step_id", "-")
        decision = ContainmentDecision(
            plan_id=plan_id,
            step_id=step_id,
            allowed=True,
            gate=gate.value,
        )

        for adapter in self.adapters:
            if adapter.gate != gate:
                continue
            try:
                res = adapter.evaluate(context)
                decision.adapters.append({
                    "adapter": adapter.name,
                    "source_repo": adapter.source_repo,
                    "allowed": res.allowed,
                    "issues": res.issues,
                    "warnings": res.warnings,
                    "score": res.score,
                    "details": res.details,
                })
                decision.warnings.extend(res.warnings)
                if not res.allowed:
                    decision.issues.extend(res.issues)
                    if self.mode == ContainmentMode.ENFORCE:
                        decision.allowed = False
            except Exception as exc:
                msg = f"{adapter.name} error: {exc}"
                decision.warnings.append(msg)
                if self.mode == ContainmentMode.ENFORCE:
                    decision.issues.append(msg)
                    decision.allowed = False

        self._audit_log.append(decision)
        return decision

    def pre_check(
        self,
        skill: SkillContract,
        inputs: Dict[str, Any],
        user_roles: Optional[List[str]] = None,
        domain_state: Optional[Dict[str, Any]] = None,
        agent_id: str = "orchestrator_001",
    ) -> ContainmentDecision:
        """Capas previas a la ejecución: gobernanza, red-team, inyección,
        stress, circuit breaker, DevOps guardrails, PII.
        """
        if self.is_killed():
            return ContainmentDecision(
                plan_id="-",
                step_id=skill.name,
                allowed=False,
                gate=Gate.PRE_ACTION.value,
                issues=["Kill switch global activado"],
            )

        context = {
            "plan_id": str(uuid.uuid4())[:8],
            "step_id": skill.name,
            "skill": skill.to_dict(),
            "inputs": inputs,
            "user_roles": user_roles or ["anonymous"],
            "domain_state": domain_state or {},
            "agent_id": agent_id,
            "failure_history": self._failure_history,
        }
        return self._run_gate(Gate.PRE_ACTION, context)

    def execution_check(
        self,
        skill: SkillContract,
        inputs: Dict[str, Any],
        signature: Optional[str] = None,
    ) -> ContainmentDecision:
        """Capa de ejecución: frontera criptográfica y firmas HMAC."""
        context = {
            "plan_id": str(uuid.uuid4())[:8],
            "step_id": skill.name,
            "skill": skill.to_dict(),
            "inputs": inputs,
            "signature": signature,
        }
        return self._run_gate(Gate.EXECUTION, context)

    def post_check(
        self,
        skill: SkillContract,
        inputs: Dict[str, Any],
        output: Dict[str, Any],
        trajectory: List[Dict[str, Any]],
        human_reviewed: bool = False,
    ) -> ContainmentDecision:
        """Capa posterior: verificación de reglas, evaluación de trayectoria
        y observaciones de seguridad.
        """
        context = {
            "plan_id": str(uuid.uuid4())[:8],
            "step_id": skill.name,
            "skill": skill.to_dict(),
            "inputs": inputs,
            "output": output,
            "trajectory": trajectory,
            "human_reviewed": human_reviewed,
        }
        return self._run_gate(Gate.POST_ACTION, context)

    # ------------------------------------------------------------------
    # Ejecución con contención
    # ------------------------------------------------------------------
    def execute_plan(
        self,
        goal: str,
        domain: str,
        user_roles: Optional[List[str]] = None,
        domain_state: Optional[Dict[str, Any]] = None,
        auto_approve: bool = False,
        signatures: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Construye un plan con el orquestador base y aplica el protocolo de
        contención en cada paso. Si un paso falla en modo `enforce`, el resto
        se aborta.
        """
        if self.mode == ContainmentMode.DISABLED:
            plan = self.orchestrator.build_plan(goal, domain, user_roles)
            plan = self.orchestrator.validate_and_execute(
                plan, user_roles, domain_state, auto_approve
            )
            return {"containment": "disabled", "plan": plan.to_dict()}

        if self.is_killed():
            return {
                "containment": "killed",
                "killed": True,
                "allowed": False,
                "issues": ["Kill switch global activado"],
                "plan": None,
            }

        signatures = signatures or {}
        plan = self.orchestrator.build_plan(goal, domain, user_roles)
        trajectory: List[Dict[str, Any]] = []
        containment_decisions: List[ContainmentDecision] = []
        sre_checks: List[Dict[str, Any]] = []

        for step in plan.steps:
            skill = self.orchestrator.skills.get(step.skill_name)
            if skill is None:
                step.status = "failed"
                step.result = {"error": f"Skill {step.skill_name} no registrada"}
                continue

            # SRE / kill switch check
            if self._sre is not None:
                sre_check = self._sre.check(skill.name)
                sre_checks.append({"skill": skill.name, **sre_check.to_dict()})
                if not sre_check.allowed and self.mode == ContainmentMode.ENFORCE:
                    step.status = "blocked"
                    step.safety_decision = {
                        "allowed": False,
                        "issues": sre_check.issues,
                        "source": "UC-324 AGT SRE",
                    }
                    break

            # Safety-critical monitor: circuit breaker + thresholds
            if self._monitor is not None:
                allowed_monitor, monitor_issues = self._monitor.can_execute(
                    skill.name,
                    latency_ms=skill.estimated_latency_ms,
                    cost=skill.estimated_cost,
                    confidence=domain_state.get("confidence") if domain_state else None,
                )
                if not allowed_monitor and self.mode == ContainmentMode.ENFORCE:
                    step.status = "blocked"
                    step.safety_decision = {
                        "allowed": False,
                        "issues": monitor_issues,
                        "source": "UC-324 safety-critical monitor",
                    }
                    self._failure_history[skill.name] = self._failure_history.get(skill.name, 0) + 1
                    break

            # Pre-action
            pre = self.pre_check(skill, step.inputs, user_roles, domain_state)
            containment_decisions.append(pre)
            if not pre.allowed and self.mode == ContainmentMode.ENFORCE:
                step.status = "blocked"
                step.safety_decision = {
                    "allowed": False,
                    "issues": pre.issues,
                    "source": "UC-324 containment pre_check",
                }
                self._failure_history[skill.name] = self._failure_history.get(skill.name, 0) + 1
                break

            # Base safety supervisor
            base_decision = self.orchestrator.safety.check(
                skill, step.inputs, user_roles or ["anonymous"], domain_state or {},
                require_human_approval=not auto_approve and skill.action_class.value in (
                    "execute", "transact", "delete"
                ),
            )
            step.safety_decision = base_decision
            if not base_decision["allowed"]:
                step.status = "blocked"
                self._failure_history[skill.name] = self._failure_history.get(skill.name, 0) + 1
                break
            if base_decision["requires_approval"] and not auto_approve:
                step.status = "awaiting_approval"
                break

            # Execution boundary (signature)
            exec_decision = self.execution_check(
                skill, step.inputs, signature=signatures.get(step.skill_name)
            )
            containment_decisions.append(exec_decision)
            if not exec_decision.allowed and self.mode == ContainmentMode.ENFORCE:
                step.status = "blocked"
                step.result = {"error": exec_decision.issues}
                self._failure_history[skill.name] = self._failure_history.get(skill.name, 0) + 1
                break

            # Ejecutar skill base
            step.status = "executed"
            step.result = self.orchestrator._execute_skill(skill, step.inputs, plan.domain)
            success = step.result.get("success", True)
            if not success:
                step.status = "failed"
                self._failure_history[skill.name] = self._failure_history.get(skill.name, 0) + 1

            # Registrar métrica SRE y safety-critical monitor
            if self._sre is not None:
                self._sre.record(skill.name, success)
            if self._monitor is not None:
                self._monitor.record(
                    skill.name,
                    success=success,
                    latency_ms=skill.estimated_latency_ms,
                    cost=skill.estimated_cost,
                    confidence=domain_state.get("confidence") if domain_state else None,
                )

            trajectory.append(step.to_dict())

            # Post-action
            # Normalizar output para que las reglas post-acción vean tanto
            # el wrapper (success) como el contenido interno de la skill.
            inner_output = step.result.get("output", {}) if isinstance(step.result, dict) else {}
            normalized_output = {
                "success": step.result.get("success") if isinstance(step.result, dict) else True,
                **(inner_output if isinstance(inner_output, dict) else {}),
                "output": inner_output,
            }
            post = self.post_check(skill, step.inputs, normalized_output, trajectory)
            containment_decisions.append(post)
            if not post.allowed and self.mode == ContainmentMode.ENFORCE:
                step.status = "blocked"
                self._failure_history[skill.name] = self._failure_history.get(skill.name, 0) + 1
                break

        plan.status = self.orchestrator._aggregate_plan_status(plan)

        blocked_statuses = {"blocked", "failed", "awaiting_approval"}
        plan_blocked = plan.status in blocked_statuses
        containment_blocked = any(
            not d.allowed and self.mode == ContainmentMode.ENFORCE
            for d in containment_decisions
        )
        sre_status = self._sre.status() if self._sre is not None else None
        monitor_status = self._monitor.status() if self._monitor is not None else None

        return {
            "containment": self.mode.value,
            "killed": self.is_killed(),
            "allowed": not (plan_blocked or containment_blocked),
            "plan": plan.to_dict(),
            "decisions": [d.to_dict() for d in containment_decisions],
            "sre_checks": sre_checks,
            "sre_status": sre_status,
            "monitor_status": monitor_status,
            "failure_history": self._failure_history.copy(),
        }

    def get_audit_log(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self._audit_log]

    # ------------------------------------------------------------------
    # Safe Shutdown Coordinator (UC-324 extension)
    # ------------------------------------------------------------------
    def safe_shutdown(
        self,
        reason: str = "manual",
        shutdown_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Initiate a safe shutdown via the SafeShutdownCoordinator.

        Coordinates with UC-300/UC-317/UC-309/UC-296/UC-326/UC-290.
        Activates the raw kill latch and builds the coordinator with injected
        adapters on first call. Does NOT recursively call kill() after the
        coordinator is initialized.
        """
        from safe_shutdown_coordinator import SafeShutdownCoordinator, build_concrete_adapters
        from safe_shutdown_models import ShutdownConfig

        # Set raw latch immediately for compatibility (is_killed() true)
        self._raw_kill()

        if self._shutdown_coordinator is None:
            adapters = self._safe_shutdown_adapters
            # If adapters were not injected but we can build from the
            # orchestrator/toolkit, prefer concrete over no-op.
            if not adapters:
                adapters = build_concrete_adapters()
            self._shutdown_coordinator = SafeShutdownCoordinator(
                config=ShutdownConfig(),
                tool_gateway=adapters.get("tool_gateway"),
                scheduler=adapters.get("scheduler"),
                observability=adapters.get("observability"),
                memory_snapshot=adapters.get("memory_snapshot"),
                reactivation_approval=adapters.get("reactivation_approval"),
            )

        status = self._shutdown_coordinator.initiate_shutdown(
            reason=reason,
            shutdown_id=shutdown_id,
            trace_id=trace_id,
        )
        return status.to_dict()

    def get_shutdown_status(self) -> Optional[Dict[str, Any]]:
        """Return the current shutdown status, or None if no coordinator."""
        if self._shutdown_coordinator is not None:
            return self._shutdown_coordinator.get_status().to_dict()
        return None

    def get_shutdown_postmortem(self) -> Optional[Dict[str, Any]]:
        """Return the last shutdown postmortem, or None."""
        if self._shutdown_coordinator is not None:
            pm = self._shutdown_coordinator.get_postmortem()
            return pm.to_dict() if pm else None
        return None

    def get_shutdown_evidence(self) -> List[Dict[str, Any]]:
        """Return the full evidence chain."""
        if self._shutdown_coordinator is not None:
            return self._shutdown_coordinator.get_evidence()
        return []

    def request_reactivation(
        self,
        shutdown_id: str,
        recovery_state_hash: str,
        reviewer_id: str,
        justification: str = "",
        ttl_seconds: float = 3600.0,
    ) -> Dict[str, Any]:
        """Request reactivation after safe shutdown.

        unkill() is NOT called here — it only happens if the coordinator
        approves. Once SAFE_STOPPED/CONTAINED, unkill() alone will not
        bypass the human-approval gate.
        """
        from safe_shutdown_coordinator import SafeShutdownCoordinator
        from safe_shutdown_models import ReactivationRequest

        if not hasattr(self, "_shutdown_coordinator"):
            return {"approved": False, "reason": "no shutdown coordinator active"}

        req = ReactivationRequest(
            shutdown_id=shutdown_id,
            recovery_state_hash=recovery_state_hash,
            reviewer_id=reviewer_id,
            justification=justification,
            ttl_seconds=ttl_seconds,
        )
        result = self._shutdown_coordinator.request_reactivation(req)
        if result.approved:
            # Only successful human-approved reactivation may unlatch the raw kill switch.
            self._raw_unkill()
            # Resume subsystem adapters
            try:
                if self._shutdown_coordinator._tool_gateway:
                    self._shutdown_coordinator._tool_gateway.resume_after_approved_reactivation(
                        self._shutdown_coordinator.shutdown_id
                    )
            except Exception:
                pass
            try:
                if self._shutdown_coordinator._scheduler:
                    self._shutdown_coordinator._scheduler.resume_after_approved_reactivation(
                        self._shutdown_coordinator.shutdown_id
                    )
            except Exception:
                pass
        return result.to_dict()
