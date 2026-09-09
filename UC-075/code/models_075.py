"""
UC-075 — Modelos de datos para Continuous Training Orchestrator.

Define estrategias de reentrenamiento (SCHEDULED, EVENT_DRIVEN, ON_DEMAND,
INCREMENTAL), triggers, resultados de gates obligatorios, decisiones
de promoción/rollback y registros de auditoría alineados con
NIST AI RMF e ISO 42001.

Cada run de pipeline queda trazado con:
- strategy_used
- drift_score
- business_trigger
- dataset_version
- model_version
- code_version
- mlflow_run_id
- decisión final y aprobador
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enumeraciones
# ---------------------------------------------------------------------------

class RetrainStrategy(str, Enum):
    """Estrategias de reentrenamiento soportadas."""
    SCHEDULED = "scheduled"            # mantenimiento periódico
    EVENT_DRIVEN = "event_driven"      # drift/error/latencia/KPI sobre umbral
    ON_DEMAND = "on_demand"            # cambio de negocio/política/datos
    INCREMENTAL = "incremental"        # aprendizaje continuo con replay


class PipelineStatus(str, Enum):
    """Estado global del run de pipeline."""
    RUNNING = "running"
    PROMOTED = "promoted"          # candidato promovido a producción
    REJECTED = "rejected"          # candidato descartado (gates fallaron)
    ROLLED_BACK = "rolled_back"    # canary falló → rollback al baseline
    PENDING_HITL = "pending_hitl"  # esperando aprobación humana UC-290
    BLOCKED = "blocked"            # política/presupuesto impidió ejecutar
    FAILED = "failed"              # error técnico en pipeline


class GateName(str, Enum):
    """Gates obligatorios, en orden canónico."""
    DRIFT = "drift_gate"
    CHAMPION_CHALLENGER = "champion_challenger_gate"
    SECURITY_FAIRNESS = "security_fairness_gate"
    HITL = "hitl_gate"
    CANARY = "canary_gate"


class GateVerdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    REQUIRES_HITL = "requires_hitl"   # no es fail: requiere decisión humana


class DecisionAction(str, Enum):
    PROMOTE = "promote"
    REJECT = "reject"
    ROLLBACK = "rollback"
    ESCALATE = "escalate"


# ---------------------------------------------------------------------------
# Política de gobernanza del orquestador
# ---------------------------------------------------------------------------

@dataclass
class OrchestratorPolicy:
    """Política de gobernanza: cuándo reentrenar, cuánto gastar, quién aprueba."""
    # Presupuesto / costo
    max_retrain_cost_usd: float = 50.0
    max_retrains_per_day: int = 4

    # Umbrales event-driven
    drift_score_threshold: float = 0.25
    error_rate_threshold: float = 0.05          # 5%
    latency_p95_degradation_pct: float = 20.0   # % peor que baseline
    user_satisfaction_threshold: float = 0.7
    calibration_error_threshold: float = 0.10

    # Champion–challenger
    min_improvement_margin: float = 0.01        # candidato debe superar en 1%
    out_of_sample_required: bool = True

    # HITL
    require_hitl_high_impact: bool = True
    high_impact_domains: List[str] = field(
        default_factory=lambda: ["medical", "legal", "financial", "military"]
    )
    auto_approve_max_risk: float = 0.3

    # Incremental learning
    incremental_max_sessions_per_day: int = 24
    replay_ratio: float = 0.2                   # 20% datos históricos anti-olvido
    catastrophic_forgetting_threshold: float = 0.05  # caída máx. en datos viejos

    # Canary
    canary_traffic_ratio: float = 0.05
    canary_min_duration_sec: float = 300.0

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


# ---------------------------------------------------------------------------
# Trigger / contexto de decisión
# ---------------------------------------------------------------------------

@dataclass
class RetrainTrigger:
    """Evento que dispara (o intenta disparar) un reentrenamiento."""
    strategy: RetrainStrategy
    reason: str
    business_trigger: str = ""          # ej. "kpi_drop", "policy_change", "data_source_change"
    metrics: Dict[str, float] = field(default_factory=dict)  # drift_score, error_rate, ...
    domain: str = "default"
    estimated_cost_usd: float = 0.0
    new_data: List[Dict[str, Any]] = field(default_factory=list)   # batch / stream
    incremental_batch: bool = False
    replay_buffer: List[Dict[str, Any]] = field(default_factory=list)  # anti-olvido
    timestamp: float = field(default_factory=time.time)
    trigger_id: str = field(default_factory=lambda: f"trg-{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "strategy": self.strategy.value,
            "reason": self.reason,
            "business_trigger": self.business_trigger,
            "metrics": self.metrics,
            "domain": self.domain,
            "estimated_cost_usd": self.estimated_cost_usd,
            "n_new_data": len(self.new_data),
            "n_replay": len(self.replay_buffer),
            "incremental_batch": self.incremental_batch,
            "timestamp": self.timestamp,
        }


@dataclass
class TriggerDecision:
    """Resultado de evaluar si un trigger procede según política/presupuesto."""
    proceed: bool
    reason: str
    policy_violations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proceed": self.proceed,
            "reason": self.reason,
            "policy_violations": self.policy_violations,
        }


# ---------------------------------------------------------------------------
# Dataset / modelo candidato
# ---------------------------------------------------------------------------

@dataclass
class FrozenDataset:
    """Snapshot inmutable de datos para el run (freeze + versionado)."""
    dataset_version: str
    dataset_hash: str
    n_records: int
    n_replay: int = 0
    frozen_at: float = field(default_factory=time.time)
    provenance: Dict[str, Any] = field(default_factory=dict)
    records: List[Dict[str, Any]] = field(default_factory=list, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_version": self.dataset_version,
            "dataset_hash": self.dataset_hash,
            "n_records": self.n_records,
            "n_replay": self.n_replay,
            "frozen_at": self.frozen_at,
            "provenance": self.provenance,
        }


@dataclass
class ChampionCandidate:
    """Par campeón (producción) vs candidato (nuevo), con métricas."""
    champion_version: str
    candidate_version: str
    champion_metrics: Dict[str, float] = field(default_factory=dict)
    candidate_metrics: Dict[str, float] = field(default_factory=dict)
    out_of_sample: bool = True
    candidate_wins: bool = False
    margin: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "champion_version": self.champion_version,
            "candidate_version": self.candidate_version,
            "champion_metrics": self.champion_metrics,
            "candidate_metrics": self.candidate_metrics,
            "out_of_sample": self.out_of_sample,
            "candidate_wins": self.candidate_wins,
            "margin": self.margin,
        }


@dataclass
class SecurityFairnessReport:
    """Resultado del gate de seguridad/fairness (sesgo, robustez, PII, backdoor)."""
    bias_detected: bool = False
    fairness_score: float = 1.0
    robustness_gap: float = 0.0
    backdoor_suspected: bool = False
    pii_in_training_data: bool = False
    violations: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not (
            self.bias_detected
            or self.backdoor_suspected
            or self.pii_in_training_data
            or self.robustness_gap > 0.15
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bias_detected": self.bias_detected,
            "fairness_score": self.fairness_score,
            "robustness_gap": self.robustness_gap,
            "backdoor_suspected": self.backdoor_suspected,
            "pii_in_training_data": self.pii_in_training_data,
            "violations": self.violations,
            "passed": self.passed,
        }


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------

@dataclass
class GateResult:
    """Resultado de un gate del pipeline."""
    gate: GateName
    verdict: GateVerdict
    score: float = 0.0
    reason: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate": self.gate.value,
            "verdict": self.verdict.value,
            "score": self.score,
            "reason": self.reason,
            "evidence": self.evidence,
        }


# ---------------------------------------------------------------------------
# Canary / promoción
# ---------------------------------------------------------------------------

@dataclass
class CanaryReport:
    """Telemetría del despliegue canary."""
    candidate_version: str
    traffic_ratio: float
    duration_sec: float
    error_rate: float = 0.0
    latency_p95_ms: float = 0.0
    baseline_latency_p95_ms: float = 0.0
    user_satisfaction: float = 1.0
    healthy: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_version": self.candidate_version,
            "traffic_ratio": self.traffic_ratio,
            "duration_sec": self.duration_sec,
            "error_rate": self.error_rate,
            "latency_p95_ms": self.latency_p95_ms,
            "baseline_latency_p95_ms": self.baseline_latency_p95_ms,
            "user_satisfaction": self.user_satisfaction,
            "healthy": self.healthy,
        }


@dataclass
class HITLApproval:
    """Registro de aprobación humana (UC-290) para promoción de alto impacto."""
    approved: bool
    approver: str = ""
    review_notes: str = ""
    approved_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "approver": self.approver,
            "review_notes": self.review_notes,
            "approved_at": self.approved_at,
        }


# ---------------------------------------------------------------------------
# Pipeline run (unidad auditable)
# ---------------------------------------------------------------------------

@dataclass
class PipelineRun:
    """Run completo del pipeline de reentrenamiento (auditable)."""
    agent_id: str
    trigger: RetrainTrigger
    run_id: str = field(default_factory=lambda: f"run-{uuid.uuid4().hex[:12]}")
    status: PipelineStatus = PipelineStatus.RUNNING

    freeze: Optional[FrozenDataset] = None
    gates: List[GateResult] = field(default_factory=list)
    matchup: Optional[ChampionCandidate] = None
    security_fairness: Optional[SecurityFairnessReport] = None
    canary: Optional[CanaryReport] = None
    approval: Optional[HITLApproval] = None

    decision: Optional[DecisionAction] = None
    decision_reason: str = ""
    rollback_version: Optional[str] = None

    strategy_used: str = ""
    code_version: str = "uc075-1.0.0"
    mlflow_run_id: str = ""

    drift_score_at_trigger: float = 0.0
    actual_cost_usd: float = 0.0
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    error: str = ""

    def finish(self, status: PipelineStatus) -> None:
        self.status = status
        self.finished_at = time.time()

    @property
    def drift_score(self) -> float:
        return float(self.trigger.metrics.get("drift_score", self.drift_score_at_trigger))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "strategy_used": self.strategy_used or self.trigger.strategy.value,
            "code_version": self.code_version,
            "mlflow_run_id": self.mlflow_run_id,
            "drift_score": round(self.drift_score, 4),
            "trigger": self.trigger.to_dict(),
            "freeze": self.freeze.to_dict() if self.freeze else None,
            "gates": [g.to_dict() for g in self.gates],
            "matchup": self.matchup.to_dict() if self.matchup else None,
            "security_fairness": self.security_fairness.to_dict()
            if self.security_fairness else None,
            "canary": self.canary.to_dict() if self.canary else None,
            "approval": self.approval.to_dict() if self.approval else None,
            "decision": self.decision.value if self.decision else None,
            "decision_reason": self.decision_reason,
            "rollback_version": self.rollback_version,
            "actual_cost_usd": self.actual_cost_usd,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Auditoría (NIST AI RMF / ISO 42001)
# ---------------------------------------------------------------------------

@dataclass
class AuditRecord:
    """Registro de auditoría inmutable por run."""
    audit_id: str = field(default_factory=lambda: f"aud-{uuid.uuid4().hex[:12]}")
    run_id: str = ""
    agent_id: str = ""
    action: str = ""               # promote, reject, rollback, escalate, blocked
    actor: str = "uc075-orchestrator"
    approver: str = ""
    rationale: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    compliance: List[str] = field(default_factory=lambda: ["nist_ai_rmf", "iso_42001"])
    timestamp: float = field(default_factory=time.time)
    previous_hash: str = ""
    record_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "action": self.action,
            "actor": self.actor,
            "approver": self.approver,
            "rationale": self.rationale,
            "evidence": self.evidence,
            "compliance": self.compliance,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "record_hash": self.record_hash,
        }
