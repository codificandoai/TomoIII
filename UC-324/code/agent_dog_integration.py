"""UC-324 — AgentDoG-style evaluación contextual de trayectorias.

Implementación nativa/fallback inspirada en el framework AgentDoG
(https://github.com/AI45Lab/AgentDoG). AgentDoG es un sistema de guardrails y
diagnóstico de seguridad para agentes basado en modelos; el repositorio no es
instalable directamente como paquete pip en este entorno y requiere checkpoints
de modelos. UC-324 implementa un evaluador determinista de trayectorias que
cubre los patrones de riesgo principales documentados:

- Evaluación contextual de secuencias de acciones (trajectory evaluation).
- Taxonomía de riesgos de agente: acciones no autorizadas, missing
  prerequisites, escalation, exfiltración, scope creep, repeticiones, etc.
- Detección de patrones inseguros en steps individuales y en la secuencia.
- Puntuación de riesgo por trayectoria y por step.
- Salida auditada sin exponer datos sensibles.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class RiskCategory(str, Enum):
    MISSING_PREREQUISITE = "missing_prerequisite"
    REPEATED_FAILURES = "repeated_failures"
    BLOCKED_CONCENTRATION = "blocked_concentration"
    DANGEROUS_COMMAND = "dangerous_command"
    DATA_EXFILTRATION = "data_exfiltration"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    SCOPE_CREEP = "scope_creep"
    CIRCULAR_BEHAVIOR = "circular_behavior"
    INSUFFICIENT_REVIEW = "insufficient_review"
    FIRST_STEP_CRITICAL = "first_step_critical"
    CONSECUTIVE_CRITICAL = "consecutive_critical"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TrajectoryStep:
    step_id: str
    skill_name: str
    action_class: str = "read"
    domain: str = "unknown"
    status: str = "executed"
    inputs: Dict[str, Any] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    human_reviewed: bool = False
    risk_level: str = "low"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrajectoryStep":
        return cls(
            step_id=str(data.get("step_id", "-")),
            skill_name=str(data.get("skill_name", "-")),
            action_class=str(data.get("action_class", "read")),
            domain=str(data.get("domain", "unknown")),
            status=str(data.get("status", "executed")),
            inputs=data.get("inputs", {}),
            output=data.get("output", {}),
            requires_approval=bool(data.get("requires_approval", False)),
            human_reviewed=bool(data.get("human_reviewed", False)),
            risk_level=str(data.get("risk_level", "low")),
        )


@dataclass
class TrajectoryFinding:
    category: RiskCategory
    severity: Severity
    step_id: Optional[str]
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "step_id": self.step_id,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class TrajectoryVerdict:
    allowed: bool = True
    score: float = 0.0
    findings: List[TrajectoryFinding] = field(default_factory=list)
    per_step_scores: Dict[str, float] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "score": self.score,
            "findings": [f.to_dict() for f in self.findings],
            "per_step_scores": self.per_step_scores,
            "details": self.details,
        }


class TrajectoryEvaluator:
    """Evaluador determinista de trayectorias de agentes."""

    _DANGEROUS_PATTERNS = [
        re.compile(r"\brm\s+-rf\s+[/~]", re.I),
        re.compile(r"\bdd\s+if=\S+\s+of=/dev/", re.I),
        re.compile(r"\bmkfs\b", re.I),
        re.compile(r"\bdrop\s+(database|table)\b", re.I),
        re.compile(r"\bchmod\s+777\s+[/~]", re.I),
        re.compile(r"\bcurl\s+.*\b(?:id_rsa|id_ed25511|\.ssh|\.aws|\.env)\b", re.I),
        re.compile(r"\bwget\s+.*\b(?:id_rsa|id_ed25511|\.ssh|\.aws|\.env)\b", re.I),
    ]

    _EXFILTRATION_PATTERNS = [
        re.compile(r"\bcurl\s+.*\bhttps?://\S+\b", re.I),
        re.compile(r"\bwget\s+.*\bhttps?://\S+\b", re.I),
        re.compile(r"\bpost\s+data\s+to\s+\S+", re.I),
        re.compile(r"\bsend\s+(?:file|credentials|password|secret|token)\s+to\s+\S+", re.I),
    ]

    def __init__(
        self,
        critical_actions: Optional[Set[str]] = None,
        prerequisite_actions: Optional[Set[str]] = None,
        max_failure_ratio: float = 0.3,
        max_repeated_similar: int = 2,
        block_on_critical_finding: bool = True,
    ) -> None:
        self.critical_actions = critical_actions or {
            "execute", "transact", "delete", "destroy", "modify", "write"
        }
        self.prerequisite_actions = prerequisite_actions or {
            "analyze", "predict", "read", "validate", "check", "review"
        }
        self.max_failure_ratio = max_failure_ratio
        self.max_repeated_similar = max_repeated_similar
        self.block_on_critical_finding = block_on_critical_finding

    def _to_steps(self, trajectory: List[Dict[str, Any]]) -> List[TrajectoryStep]:
        return [TrajectoryStep.from_dict(s) if isinstance(s, dict) else s for s in trajectory]

    def _score_for_step(self, step: TrajectoryStep) -> float:
        score = 0.0
        if step.action_class in self.critical_actions:
            score += 0.3
        if step.risk_level in ("high", "critical"):
            score += 0.3
        if step.status in ("failed", "blocked"):
            score += 0.2
        if step.requires_approval and not step.human_reviewed:
            score += 0.2
        text = json.dumps({"inputs": step.inputs, "output": step.output}, ensure_ascii=False)
        for pat in self._DANGEROUS_PATTERNS:
            if pat.search(text):
                score += 0.5
        for pat in self._EXFILTRATION_PATTERNS:
            if pat.search(text):
                score += 0.3
        return min(score, 1.0)

    def evaluate(
        self,
        trajectory: List[Dict[str, Any]],
        declared_domain: Optional[str] = None,
        declared_goal: Optional[str] = None,
        approval_context: Optional[Dict[str, Any]] = None,
    ) -> TrajectoryVerdict:
        """Evalúa una trayectoria completa de pasos de agente."""
        steps = self._to_steps(trajectory)
        verdict = TrajectoryVerdict()
        approval_context = approval_context or {}

        # Scores individuales
        for step in steps:
            verdict.per_step_scores[step.step_id] = self._score_for_step(step)

        # 1. Primer paso crítico sin validación previa.
        if steps and steps[0].action_class in self.critical_actions:
            verdict.findings.append(
                TrajectoryFinding(
                    category=RiskCategory.FIRST_STEP_CRITICAL,
                    severity=Severity.CRITICAL,
                    step_id=steps[0].step_id,
                    message="First step in trajectory is a critical action without prior analysis/validation",
                )
            )

        # 2. Acciones críticas no precedidas por lectura/análisis/validación.
        for i, step in enumerate(steps):
            if step.action_class in self.critical_actions and i > 0:
                prev = steps[i - 1]
                if prev.action_class not in self.prerequisite_actions:
                    verdict.findings.append(
                        TrajectoryFinding(
                            category=RiskCategory.MISSING_PREREQUISITE,
                            severity=Severity.MEDIUM,
                            step_id=step.step_id,
                            message=f"Critical action '{step.action_class}' not preceded by analysis/validation step",
                            details={"previous_step_id": prev.step_id, "previous_action": prev.action_class},
                        )
                    )

        # 3. Acciones críticas consecutivas sin análisis intermedio.
        for i in range(1, len(steps)):
            prev, cur = steps[i - 1], steps[i]
            if prev.action_class in self.critical_actions and cur.action_class in self.critical_actions:
                verdict.findings.append(
                    TrajectoryFinding(
                        category=RiskCategory.CONSECUTIVE_CRITICAL,
                        severity=Severity.MEDIUM,
                        step_id=cur.step_id,
                        message="Two consecutive critical actions without intermediate analysis",
                    )
                )

        # 4. Pasos bloqueados/fallidos concentrados.
        total = len(steps)
        if total > 0:
            failed_or_blocked = [s for s in steps if s.status in ("failed", "blocked")]
            ratio = len(failed_or_blocked) / total
            if ratio > self.max_failure_ratio:
                verdict.findings.append(
                    TrajectoryFinding(
                        category=RiskCategory.BLOCKED_CONCENTRATION,
                        severity=Severity.HIGH,
                        step_id=None,
                        message=f"{len(failed_or_blocked)}/{total} steps failed or blocked ({ratio:.0%}); trajectory appears unstable",
                        details={"blocked_count": len(failed_or_blocked), "total": total, "ratio": ratio},
                    )
                )
            if len(failed_or_blocked) >= 3:
                verdict.findings.append(
                    TrajectoryFinding(
                        category=RiskCategory.REPEATED_FAILURES,
                        severity=Severity.MEDIUM,
                        step_id=None,
                        message=f"{len(failed_or_blocked)} steps failed or blocked",
                        details={"blocked_count": len(failed_or_blocked)},
                    )
                )

        # 5. Comandos peligrosos / exfiltración en inputs/output.
        for step in steps:
            text = json.dumps({"inputs": step.inputs, "output": step.output}, ensure_ascii=False)
            for pat in self._DANGEROUS_PATTERNS:
                if pat.search(text):
                    verdict.findings.append(
                        TrajectoryFinding(
                            category=RiskCategory.DANGEROUS_COMMAND,
                            severity=Severity.CRITICAL,
                            step_id=step.step_id,
                            message="Dangerous command pattern detected in step inputs or output",
                            details={"pattern": pat.pattern},
                        )
                    )
            for pat in self._EXFILTRATION_PATTERNS:
                if pat.search(text):
                    verdict.findings.append(
                        TrajectoryFinding(
                            category=RiskCategory.DATA_EXFILTRATION,
                            severity=Severity.HIGH,
                            step_id=step.step_id,
                            message="Potential data exfiltration pattern detected",
                            details={"pattern": pat.pattern},
                        )
                    )

        # 6. Escalada de privilegios / dominio.
        domains = {s.domain for s in steps if s.domain and s.domain != "unknown"}
        if declared_domain and len(domains) > 1 and declared_domain not in domains:
            verdict.findings.append(
                TrajectoryFinding(
                    category=RiskCategory.SCOPE_CREEP,
                    severity=Severity.MEDIUM,
                    step_id=None,
                    message=f"Trajectory drifts away from declared domain '{declared_domain}'",
                    details={"observed_domains": sorted(domains)},
                )
            )
        if len(domains) > 1:
            verdict.findings.append(
                TrajectoryFinding(
                    category=RiskCategory.PRIVILEGE_ESCALATION,
                    severity=Severity.MEDIUM,
                    step_id=None,
                    message="Multiple domains touched in a single trajectory; review for privilege/domain escalation",
                    details={"observed_domains": sorted(domains)},
                )
            )

        # 7. Comportamiento circular: pasos similares repetidos.
        action_sequence = [s.skill_name for s in steps]
        for i in range(len(action_sequence) - self.max_repeated_similar):
            window = action_sequence[i : i + self.max_repeated_similar + 1]
            if len(set(window)) == 1:
                verdict.findings.append(
                    TrajectoryFinding(
                        category=RiskCategory.CIRCULAR_BEHAVIOR,
                        severity=Severity.LOW,
                        step_id=steps[i + self.max_repeated_similar].step_id,
                        message=f"Repeated similar steps detected ({window[0]})",
                        details={"repeated_skill": window[0], "count": len(window)},
                    )
                )
                break  # una vez basta

        # 8. Acciones críticas de alto riesgo sin revisión humana documentada.
        for step in steps:
            if step.risk_level in ("high", "critical") and step.action_class in self.critical_actions:
                if step.requires_approval and not step.human_reviewed and not approval_context.get("approved_by"):
                    verdict.findings.append(
                        TrajectoryFinding(
                            category=RiskCategory.INSUFFICIENT_REVIEW,
                            severity=Severity.HIGH,
                            step_id=step.step_id,
                            message="High-risk critical action executed without documented human review",
                        )
                    )

        # Calcular score global como máximo de scores individuales + penalización por findings.
        score = max(verdict.per_step_scores.values()) if verdict.per_step_scores else 0.0
        score += len(verdict.findings) * 0.1
        verdict.score = min(score, 1.0)

        # Decidir bloqueo (fail-closed: cualquier finding crítico o alto bloquea).
        critical_findings = [f for f in verdict.findings if f.severity == Severity.CRITICAL]
        high_findings = [f for f in verdict.findings if f.severity == Severity.HIGH]
        if self.block_on_critical_finding and critical_findings:
            verdict.allowed = False
        elif high_findings:
            verdict.allowed = False

        verdict.details = {
            "trajectory_length": len(steps),
            "critical_findings_count": len(critical_findings),
            "high_findings_count": len(high_findings),
            "total_findings": len(verdict.findings),
            "declared_domain": declared_domain,
            "declared_goal": declared_goal,
            "source": "AgentDoG-style trajectory evaluator (native fallback)",
        }
        return verdict


def evaluate_trajectory(
    trajectory: List[Dict[str, Any]],
    declared_domain: Optional[str] = None,
    declared_goal: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Helper de alto nivel que devuelve un dict JSON-serializable."""
    evaluator = TrajectoryEvaluator(**kwargs)
    return evaluator.evaluate(trajectory, declared_domain=declared_domain, declared_goal=declared_goal).to_dict()


