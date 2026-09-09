"""
UC-075 — Risk Management Framework para ecosistemas AGI/MLOps.

Extensión de gobernanza que identifica, clasifica, prioriza y gestiona riesgos
proactivamente siguiendo NIST AI RMF, ISO 42001, GDPR y la Ley de IA de la UE.

Cubre las categorías de riesgo:
- Datos: drift, PII leak, data poisoning, calidad, procedencia.
- Modelo: sobreajuste, sesgo, adversarial, alucinación, explicabilidad.
- Agente: autonomía excesiva, prompt injection, abuso de herramientas, cascada.
- Infraestructura: downtime, misconfig, secret leak, supply chain.
- Organizativo: falta de ownership, separación de funciones, respuesta a incidentes.
- Regulatorio/negocio: sanciones, pérdida de ingresos, pérdida de confianza.

El marco proporciona:
- Risk: activo de riesgo cuantificado (probabilidad, impacto, exposición, eficacia de controles).
- RiskScorer: cálculo residual y severidad.
- RiskRegister: inventario inmutable, tendencias y recomendaciones.
- ProactiveRiskPlan: umbrales, revisiones periódicas, alertas.
- RiskGate: gate de UC-075 que bloquea/escala a HITL según riesgo residual.
- RunbookCatalog: acciones de respuesta por categoría.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RiskCategory(str, Enum):
    DATA = "data"
    MODEL = "model"
    AGENT = "agent"
    INFRASTRUCTURE = "infrastructure"
    ORGANIZATIONAL = "organizational"
    REGULATORY = "regulatory"
    SECURITY = "security"
    BUSINESS = "business"


class RiskSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class RiskStatus(str, Enum):
    OPEN = "open"
    MITIGATED = "mitigated"
    ACCEPTED = "accepted"
    TRANSFERRED = "transferred"
    CLOSED = "closed"
    ESCALATED = "escalated"


class RiskTrend(str, Enum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"


# ---------------------------------------------------------------------------
# Entidad de riesgo
# ---------------------------------------------------------------------------


@dataclass
class Risk:
    """Riesgo individual del ecosistema AGI/MLOps."""

    risk_id: str = field(default_factory=lambda: f"risk-{uuid.uuid4().hex[:10]}")
    category: RiskCategory = RiskCategory.DATA
    subcategory: str = ""  # ej. "data_poisoning", "prompt_injection"
    description: str = ""
    # Factores cuantitativos 0..1
    probability: float = 0.0
    impact: float = 0.0
    exposure: float = 1.0
    control_effectiveness: float = 0.0
    residual_risk: float = field(init=False)
    inherent_risk: float = field(init=False)
    severity: RiskSeverity = field(init=False)  # type: ignore
    status: RiskStatus = RiskStatus.OPEN
    trend: RiskTrend = RiskTrend.STABLE
    owner: str = ""
    detected_at: float = field(default_factory=time.time)
    review_due_at: float = field(default_factory=lambda: time.time() + 7 * 86400)
    # Vínculos
    linked_artifact_ids: List[str] = field(default_factory=list)
    linked_run_ids: List[str] = field(default_factory=list)
    linked_agent_ids: List[str] = field(default_factory=list)
    # Trigger / causa técnica detectada
    trigger_event: str = ""
    trigger_details: Dict[str, Any] = field(default_factory=dict)
    # Controles aplicados o recomendados
    mitigations: List[str] = field(default_factory=list)
    auto_controls: List[str] = field(default_factory=list)
    requires_hitl: bool = False
    requires_freeze: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        self.inherent_risk = max(0.0, min(1.0, self.probability)) * \
                            max(0.0, min(1.0, self.impact)) * \
                            max(0.0, min(1.0, self.exposure))
        effectiveness = max(0.0, min(1.0, self.control_effectiveness))
        self.residual_risk = max(0.0, self.inherent_risk - effectiveness)
        self.severity = RiskScorer.severity(self.residual_risk)

    def recompute(self) -> None:
        self.inherent_risk = max(0.0, min(1.0, self.probability)) * \
                            max(0.0, min(1.0, self.impact)) * \
                            max(0.0, min(1.0, self.exposure))
        effectiveness = max(0.0, min(1.0, self.control_effectiveness))
        self.residual_risk = max(0.0, self.inherent_risk - effectiveness)
        self.severity = RiskScorer.severity(self.residual_risk)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "category": self.category.value,
            "subcategory": self.subcategory,
            "description": self.description,
            "probability": round(self.probability, 4),
            "impact": round(self.impact, 4),
            "exposure": round(self.exposure, 4),
            "control_effectiveness": round(self.control_effectiveness, 4),
            "inherent_risk": round(self.inherent_risk, 4),
            "residual_risk": round(self.residual_risk, 4),
            "severity": self.severity.value,
            "status": self.status.value,
            "trend": self.trend.value,
            "owner": self.owner,
            "detected_at": self.detected_at,
            "review_due_at": self.review_due_at,
            "linked_artifact_ids": self.linked_artifact_ids,
            "linked_run_ids": self.linked_run_ids,
            "linked_agent_ids": self.linked_agent_ids,
            "trigger_event": self.trigger_event,
            "trigger_details": self.trigger_details,
            "mitigations": self.mitigations,
            "auto_controls": self.auto_controls,
            "requires_hitl": self.requires_hitl,
            "requires_freeze": self.requires_freeze,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Scorer y severidad
# ---------------------------------------------------------------------------


class RiskScorer:
    THRESHOLDS = {
        RiskSeverity.CRITICAL: 0.80,
        RiskSeverity.HIGH: 0.60,
        RiskSeverity.MEDIUM: 0.35,
        RiskSeverity.LOW: 0.15,
        RiskSeverity.NEGLIGIBLE: 0.0,
    }

    @staticmethod
    def severity(residual: float) -> RiskSeverity:
        for sev, threshold in sorted(RiskScorer.THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
            if residual >= threshold:
                return sev
        return RiskSeverity.NEGLIGIBLE

    @staticmethod
    def classify_many(risks: List[Risk]) -> Dict[str, Any]:
        by_severity: Dict[str, int] = {s.value: 0 for s in RiskSeverity}
        total_residual = 0.0
        max_risk = 0.0
        for r in risks:
            by_severity[r.severity.value] += 1
            total_residual += r.residual_risk
            max_risk = max(max_risk, r.residual_risk)
        return {
            "total_risks": len(risks),
            "by_severity": by_severity,
            "aggregate_residual_risk": round(total_residual, 4),
            "max_residual_risk": round(max_risk, 4),
        }


# ---------------------------------------------------------------------------
# Registro de riesgos
# ---------------------------------------------------------------------------


class RiskRegister:
    """Inventario de riesgos con historial y tendencias."""

    def __init__(self) -> None:
        self._risks: Dict[str, Risk] = {}
        self._history: List[Dict[str, Any]] = []

    def register(self, risk: Risk) -> Risk:
        self._risks[risk.risk_id] = risk
        self._history.append({
            "event": "registered",
            "risk_id": risk.risk_id,
            "timestamp": time.time(),
            "residual_risk": risk.residual_risk,
        })
        return risk

    def get(self, risk_id: str) -> Optional[Risk]:
        return self._risks.get(risk_id)

    def update(
        self,
        risk_id: str,
        mitigations: Optional[List[str]] = None,
        control_effectiveness: Optional[float] = None,
        status: Optional[RiskStatus] = None,
        notes: str = "",
    ) -> Optional[Risk]:
        risk = self._risks.get(risk_id)
        if risk is None:
            return None
        if mitigations:
            risk.mitigations.extend(mitigations)
        if control_effectiveness is not None:
            risk.control_effectiveness = control_effectiveness
        if status is not None:
            risk.status = status
        if notes:
            risk.notes += "; " + notes
        risk.recompute()
        self._history.append({
            "event": "updated",
            "risk_id": risk_id,
            "timestamp": time.time(),
            "residual_risk": risk.residual_risk,
            "status": risk.status.value,
        })
        return risk

    def list(
        self,
        category: Optional[RiskCategory] = None,
        status: Optional[RiskStatus] = None,
        severity: Optional[RiskSeverity] = None,
    ) -> List[Risk]:
        result = list(self._risks.values())
        if category:
            result = [r for r in result if r.category == category]
        if status:
            result = [r for r in result if r.status == status]
        if severity:
            result = [r for r in result if r.severity == severity]
        return result

    def classify(self) -> Dict[str, Any]:
        return RiskScorer.classify_many(list(self._risks.values()))

    def summary(self) -> Dict[str, Any]:
        return {
            "total_risks": len(self._risks),
            "classification": self.classify(),
            "open_high_critical": len([
                r for r in self._risks.values()
                if r.status == RiskStatus.OPEN and r.severity in (RiskSeverity.HIGH, RiskSeverity.CRITICAL)
            ]),
            "requires_hitl": [r.risk_id for r in self._risks.values() if r.requires_hitl and r.status == RiskStatus.OPEN],
        }

    def history(self) -> List[Dict[str, Any]]:
        return list(self._history)


# ---------------------------------------------------------------------------
# Plan de riesgos proactivo
# ---------------------------------------------------------------------------


@dataclass
class RiskPolicy:
    """Umbrales de tolerancia al riesgo y acciones automáticas."""

    max_residual_for_auto_promote: float = 0.30
    max_aggregate_residual: float = 1.50
    hitl_threshold_severity: RiskSeverity = RiskSeverity.HIGH
    freeze_threshold_severity: RiskSeverity = RiskSeverity.CRITICAL
    review_interval_days: int = 7
    auto_escalate_categories: Set[RiskCategory] = field(default_factory=lambda: {
        RiskCategory.AGENT, RiskCategory.SECURITY, RiskCategory.REGULATORY,
    })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_residual_for_auto_promote": self.max_residual_for_auto_promote,
            "max_aggregate_residual": self.max_aggregate_residual,
            "hitl_threshold_severity": self.hitl_threshold_severity.value,
            "freeze_threshold_severity": self.freeze_threshold_severity.value,
            "review_interval_days": self.review_interval_days,
            "auto_escalate_categories": [c.value for c in self.auto_escalate_categories],
        }


class ProactiveRiskPlan:
    """Genera revisiones y recomendaciones proactivas."""

    def __init__(self, policy: Optional[RiskPolicy] = None) -> None:
        self.policy = policy or RiskPolicy()

    def review_due(self, risk: Risk) -> bool:
        return time.time() >= risk.review_due_at

    def recommend_action(self, risk: Risk) -> str:
        if risk.residual_risk >= RiskScorer.THRESHOLDS[self.policy.freeze_threshold_severity]:
            return "freeze_and_escalate"
        if risk.residual_risk >= RiskScorer.THRESHOLDS[self.policy.hitl_threshold_severity]:
            return "requires_hitl_review"
        if risk.category in self.policy.auto_escalate_categories and risk.severity in (RiskSeverity.HIGH, RiskSeverity.CRITICAL):
            return "auto_escalate_to_security"
        if risk.status == RiskStatus.OPEN and risk.residual_risk > 0.05:
            return "apply_mitigation"
        return "monitor"

    def next_steps(self, register: RiskRegister) -> List[Dict[str, Any]]:
        actions = []
        for risk in register.list(status=RiskStatus.OPEN):
            action = self.recommend_action(risk)
            due = self.review_due(risk)
            actions.append({
                "risk_id": risk.risk_id,
                "category": risk.category.value,
                "severity": risk.severity.value,
                "residual_risk": round(risk.residual_risk, 4),
                "recommendation": action,
                "review_due": due,
                "owner": risk.owner,
            })
        return actions


# ---------------------------------------------------------------------------
# Runbooks por categoría de riesgo
# ---------------------------------------------------------------------------


class RunbookCatalog:
    """Catálogo de acciones de respuesta a incidentes por categoría."""

    DEFAULT_RUNBOOKS: Dict[RiskCategory, Dict[str, Any]] = {
        RiskCategory.DATA: {
            "name": "Data compromise response",
            "steps": [
                "Freeze dataset version and revoke access to untrusted sources.",
                "Run PII/secret scan over affected artifacts.",
                "Quarantine poisoned or drifted micro-batches.",
                "Notify data owner and privacy officer.",
            ],
            "auto_controls": ["freeze_dataset", "quarantine_microbatch", "revoke_rag_source"],
        },
        RiskCategory.MODEL: {
            "name": "Model integrity response",
            "steps": [
                "Promote last known-good champion from registry.",
                "Run adversarial and bias test suite.",
                "Shadow canary any candidate with unexplained behavior.",
                "Capture artifacts and model card for forensic review.",
            ],
            "auto_controls": ["rollback_model", "shadow_canary", "disable_auto_promote"],
        },
        RiskCategory.AGENT: {
            "name": "Agent autonomy / tool abuse response",
            "steps": [
                "Revoke short-lived credentials and suspend tool access.",
                "Put agent in read-only / human-approval mode.",
                "Trace plan, tool calls and parameters through audit log.",
                "Disable affected tools until root cause is confirmed.",
            ],
            "auto_controls": ["revoke_credentials", "disable_tool", "require_hitl", "isolate_agent"],
        },
        RiskCategory.INFRASTRUCTURE: {
            "name": "Infrastructure compromise response",
            "steps": [
                "Rotate exposed secrets and rebuild affected containers.",
                "Check IaC drift and SBOM for vulnerable dependencies.",
                "Failover to secondary region if availability is impacted.",
                "Block traffic from untrusted sources.",
            ],
            "auto_controls": ["rotate_secrets", "failover_region", "block_traffic", "rebuild_image"],
        },
        RiskCategory.ORGANIZATIONAL: {
            "name": "Governance gap response",
            "steps": [
                "Assign risk owner and update asset inventory.",
                "Document decision chain and approval matrix.",
                "Schedule tabletop exercise and policy review.",
                "Enable mandatory training for operators.",
            ],
            "auto_controls": ["assign_owner", "update_inventory", "schedule_review"],
        },
        RiskCategory.REGULATORY: {
            "name": "Regulatory breach response",
            "steps": [
                "Preserve evidence and legal hold on artifacts.",
                "Notify DPO/legal team within SLA.",
                "Restrict cross-border replication of affected data.",
                "Prepare regulatory report with audit trail.",
            ],
            "auto_controls": ["legal_hold", "block_replication", "preserve_evidence"],
        },
        RiskCategory.SECURITY: {
            "name": "Security incident response",
            "steps": [
                "Contain compromised scope and revoke sessions.",
                "Capture logs and traces for forensic analysis.",
                "Patch or update vulnerable components.",
                "Engage red team / incident response team.",
            ],
            "auto_controls": ["revoke_sessions", "patch_component", "enable_logging"],
        },
        RiskCategory.BUSINESS: {
            "name": "Business impact response",
            "steps": [
                "Quantify financial and reputational impact.",
                "Communicate to stakeholders with approved messaging.",
                "Trigger business continuity plan if needed.",
                "Review insurance / contractual coverage.",
            ],
            "auto_controls": ["notify_stakeholders", "trigger_bcp"],
        },
    }

    def __init__(self, runbooks: Optional[Dict[RiskCategory, Dict[str, Any]]] = None) -> None:
        self._runbooks = runbooks or dict(self.DEFAULT_RUNBOOKS)

    def get(self, category: RiskCategory) -> Dict[str, Any]:
        return self._runbooks.get(category, {
            "name": "Generic response",
            "steps": ["Assess impact.", "Contain scope.", "Notify owner.", "Review controls."],
            "auto_controls": ["notify_owner"],
        })

    def all(self) -> Dict[str, Any]:
        return {cat.value: book for cat, book in self._runbooks.items()}


# ---------------------------------------------------------------------------
# RiskGate para el pipeline UC-075
# ---------------------------------------------------------------------------


@dataclass
class RiskGateResult:
    passed: bool
    requires_hitl: bool
    requires_freeze: bool
    reason: str
    max_residual_risk: float = 0.0
    aggregate_residual_risk: float = 0.0
    blocking_risks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "requires_hitl": self.requires_hitl,
            "requires_freeze": self.requires_freeze,
            "reason": self.reason,
            "max_residual_risk": round(self.max_residual_risk, 4),
            "aggregate_residual_risk": round(self.aggregate_residual_risk, 4),
            "blocking_risks": self.blocking_risks,
        }


class RiskGate:
    """Gate de riesgo que evalúa el registro antes de promociones."""

    def __init__(
        self,
        register: Optional[RiskRegister] = None,
        policy: Optional[RiskPolicy] = None,
        proactive_plan: Optional[ProactiveRiskPlan] = None,
    ) -> None:
        self.register = register or RiskRegister()
        self.policy = policy or RiskPolicy()
        self.plan = proactive_plan or ProactiveRiskPlan(self.policy)

    def evaluate(
        self,
        artifact_ids: Optional[List[str]] = None,
        run_id: Optional[str] = None,
        agent_ids: Optional[List[str]] = None,
    ) -> RiskGateResult:
        """Evalúa riesgos abiertos vinculados a los artefactos/runs/agentes."""
        risks = self.register.list(status=RiskStatus.OPEN)
        if artifact_ids:
            risks = [r for r in risks if any(a in r.linked_artifact_ids for a in artifact_ids)]
        if run_id:
            risks = [r for r in risks if run_id in r.linked_run_ids]
        if agent_ids:
            risks = [r for r in risks if any(a in r.linked_agent_ids for a in agent_ids)]

        if not risks:
            return RiskGateResult(
                passed=True,
                requires_hitl=False,
                requires_freeze=False,
                reason="No open risks linked to promotion scope.",
            )

        max_residual = max(r.residual_risk for r in risks)
        aggregate = sum(r.residual_risk for r in risks)
        blocking = [r.risk_id for r in risks if r.severity == RiskSeverity.CRITICAL]
        requires_hitl = any(
            r.severity.value in (RiskSeverity.HIGH.value, RiskSeverity.CRITICAL.value)
            for r in risks
        )

        if blocking or max_residual >= self.policy.max_residual_for_auto_promote:
            return RiskGateResult(
                passed=False,
                requires_hitl=bool(blocking) or requires_hitl,
                requires_freeze=bool(blocking),
                reason=(
                    f"Blocking risks present: {blocking} "
                    f"(max residual {max_residual:.4f} >= {self.policy.max_residual_for_auto_promote})."
                ),
                max_residual_risk=max_residual,
                aggregate_residual_risk=aggregate,
                blocking_risks=blocking,
            )

        if aggregate > self.policy.max_aggregate_residual:
            return RiskGateResult(
                passed=False,
                requires_hitl=True,
                requires_freeze=False,
                reason=(
                    f"Aggregate residual risk {aggregate:.4f} exceeds policy "
                    f"{self.policy.max_aggregate_residual}."
                ),
                max_residual_risk=max_residual,
                aggregate_residual_risk=aggregate,
            )

        return RiskGateResult(
            passed=True,
            requires_hitl=requires_hitl,
            requires_freeze=False,
            reason="Risks within tolerance; HITL recommended for high-severity items.",
            max_residual_risk=max_residual,
            aggregate_residual_risk=aggregate,
        )


# ---------------------------------------------------------------------------
# Helpers: convertir eventos del ecosistema a riesgos
# ---------------------------------------------------------------------------


def risk_from_gate_failure(
    category: RiskCategory,
    subcategory: str,
    description: str,
    gate_name: str,
    reason: str,
    run_id: str = "",
    artifact_ids: Optional[List[str]] = None,
    probability: float = 0.7,
    impact: float = 0.7,
    exposure: float = 1.0,
    control_effectiveness: float = 0.0,
) -> Risk:
    return Risk(
        category=category,
        subcategory=subcategory,
        description=description,
        probability=probability,
        impact=impact,
        exposure=exposure,
        control_effectiveness=control_effectiveness,
        trigger_event=f"{gate_name}_failure",
        trigger_details={"gate": gate_name, "reason": reason},
        linked_run_ids=[run_id] if run_id else [],
        linked_artifact_ids=artifact_ids or [],
        auto_controls=["block_promotion", "require_review"],
        requires_hitl=True,
    )


def risk_from_online_quarantine(
    learner_id: str,
    reason: str,
    batch_id: str,
    artifact_ids: Optional[List[str]] = None,
    probability: float = 0.6,
    impact: float = 0.5,
) -> Risk:
    return Risk(
        category=RiskCategory.DATA,
        subcategory="online_microbatch_quarantine",
        description=f"Online learner {learner_id} quarantined micro-batch {batch_id}: {reason}",
        probability=probability,
        impact=impact,
        exposure=0.8,
        trigger_event="uc075_microbatch_quarantined",
        trigger_details={"learner_id": learner_id, "batch_id": batch_id, "reason": reason},
        linked_artifact_ids=artifact_ids or [],
        linked_agent_ids=[learner_id],
        auto_controls=["quarantine_batch", "open_circuit_breaker"],
    )


def risk_from_drift(
    drift_score: float,
    run_id: str = "",
    artifact_ids: Optional[List[str]] = None,
) -> Risk:
    impact = min(1.0, drift_score)
    return Risk(
        category=RiskCategory.DATA,
        subcategory="data_drift",
        description=f"Data drift detected with score {drift_score:.4f}",
        probability=0.8,
        impact=impact,
        exposure=0.9,
        trigger_event="drift_exceeded",
        trigger_details={"drift_score": drift_score},
        linked_run_ids=[run_id] if run_id else [],
        linked_artifact_ids=artifact_ids or [],
        auto_controls=["trigger_retrain", "freeze_baseline"],
    )


def risk_from_agent_tool_abuse(
    agent_id: str,
    tool_name: str,
    reason: str,
    probability: float = 0.8,
    impact: float = 0.9,
) -> Risk:
    return Risk(
        category=RiskCategory.AGENT,
        subcategory="tool_abuse",
        description=f"Agent {agent_id} used tool {tool_name} inappropriately: {reason}",
        probability=probability,
        impact=impact,
        exposure=1.0,
        trigger_event="agent_tool_abuse",
        trigger_details={"agent_id": agent_id, "tool_name": tool_name, "reason": reason},
        linked_agent_ids=[agent_id],
        auto_controls=["revoke_credentials", "disable_tool", "require_hitl"],
        requires_hitl=True,
    )


def risk_from_supply_chain(
    component: str,
    reason: str,
    artifact_ids: Optional[List[str]] = None,
) -> Risk:
    return Risk(
        category=RiskCategory.INFRASTRUCTURE,
        subcategory="supply_chain_compromise",
        description=f"Supply chain issue in {component}: {reason}",
        probability=0.5,
        impact=0.8,
        exposure=0.9,
        trigger_event="supply_chain_alert",
        trigger_details={"component": component, "reason": reason},
        linked_artifact_ids=artifact_ids or [],
        auto_controls=["block_component", "rebuild_image", "scan_sbom"],
        requires_hitl=True,
    )
