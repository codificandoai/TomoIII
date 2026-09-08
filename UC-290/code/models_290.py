"""
UC-290 — Modelos de datos para HITL con Razonamiento Transparente.

Define:
- Configuración del guardian HITL.
- Enumeraciones para decisiones, riesgo, acciones humanas.
- Expediente de Decisión (DecisionDossier).
- Pasos de razonamiento.
- Resultado de revisión humana.
- Resultado del pipeline HITL.
"""

import time
import uuid
import hashlib
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


# ---------------------------------------------------------------------------
# Enumeraciones
# ---------------------------------------------------------------------------

class RiskLevel(str, Enum):
    """Niveles de riesgo para una decisión."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HITLDecision(str, Enum):
    """Decisión del pipeline HITL."""
    AUTO_EXECUTE = "auto_execute"
    ESCALATE = "escalate"
    SAFE_HOLD = "safe_hold"
    APPROVED = "approved"
    MODIFIED = "modified"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"


class HumanAction(str, Enum):
    """Acción que un revisor humano puede tomar."""
    APPROVE = "approve"
    MODIFY = "modify"
    REJECT = "reject"
    REQUEST_MORE_INFO = "request_more_info"
    DELEGATE = "delegate"


class DossierStatus(str, Enum):
    """Estado del expediente de decisión."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    SAFE_HOLD = "safe_hold"
    APPROVED = "approved"
    MODIFIED = "modified"
    REJECTED = "rejected"
    EXPIRED = "expired"
    AUTO_EXECUTED = "auto_executed"


class ReasoningStepType(str, Enum):
    """Tipo de paso de razonamiento."""
    DATA = "data"
    INFERENCE = "inference"
    PROJECTION = "projection"
    VALIDATION = "validation"
    CONFLICT = "conflict"
    REFLECTION = "reflection"
    SUGGESTION = "suggestion"


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

@dataclass
class HITLConfig:
    """Configuración del guardian HITL."""
    # Umbrales de riesgo
    confidence_threshold: float = 0.65
    risk_high_threshold: float = 0.70
    risk_critical_threshold: float = 0.90
    volatility_threshold: float = 0.05  # 5% movimiento

    # Timeouts
    escalation_timeout_sec: float = 3600.0  # 1 hora
    auto_execute_max_risk: float = 0.30  # Riesgo máximo para auto-execute

    # Governance
    require_human_for_critical: bool = True
    require_human_for_high_risk: bool = True
    allow_auto_execute_low_risk: bool = True
    max_auto_confidence: float = 0.85  # Confiar hasta 85% sin humano

    # Audit
    audit_hash_algorithm: str = "sha256"
    retain_dossiers: int = 1000

    # Integración
    uc315_source_tag: str = "uc315_decision"
    uc324_containment_tag: str = "uc324_containment"
    uc087_integrity_tag: str = "uc087_integrity"
    uc162_llmops_tag: str = "uc162_llmops"
    uc325_reflection_tag: str = "uc325_reflection"
    uc322_conflict_tag: str = "uc322_conflict"
    uc329_graph_tag: str = "uc329_graph"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "confidence_threshold": self.confidence_threshold,
            "risk_high_threshold": self.risk_high_threshold,
            "risk_critical_threshold": self.risk_critical_threshold,
            "volatility_threshold": self.volatility_threshold,
            "escalation_timeout_sec": self.escalation_timeout_sec,
            "auto_execute_max_risk": self.auto_execute_max_risk,
            "require_human_for_critical": self.require_human_for_critical,
            "require_human_for_high_risk": self.require_human_for_high_risk,
            "allow_auto_execute_low_risk": self.allow_auto_execute_low_risk,
            "max_auto_confidence": self.max_auto_confidence,
            "audit_hash_algorithm": self.audit_hash_algorithm,
            "retain_dossiers": self.retain_dossiers,
        }


# ---------------------------------------------------------------------------
# Razonamiento
# ---------------------------------------------------------------------------

@dataclass
class ReasoningStep:
    """Un paso individual del razonamiento transparente."""
    step_number: int
    step_type: ReasoningStepType
    description: str
    evidence: str = ""
    confidence: float = 0.0
    source: str = ""  # qué UC produjo este paso

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "step_type": self.step_type.value if isinstance(self.step_type, ReasoningStepType) else self.step_type,
            "description": self.description,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "source": self.source,
        }


# ---------------------------------------------------------------------------
# Datos de entrada
# ---------------------------------------------------------------------------

@dataclass
class DecisionInput:
    """
    Datos procesados que alimentan la decisión de UC-315.
    Incluye validaciones de capas externas.
    """
    # Identificación
    decision_id: str = ""
    trace_id: str = ""

    # Datos del contexto
    context: Dict[str, Any] = field(default_factory=dict)

    # Sugerencia de la IA (UC-315)
    ai_suggestion: str = ""
    ai_confidence: float = 0.0
    ai_reasoning_steps: List[ReasoningStep] = field(default_factory=list)

    # Validaciones de capas externas
    uc087_integrity_passed: bool = False
    uc087_integrity_details: Dict[str, Any] = field(default_factory=dict)

    uc162_llmops_passed: bool = False
    uc162_llmops_details: Dict[str, Any] = field(default_factory=dict)

    uc325_reflection_score: float = 0.0
    uc325_reflection_details: Dict[str, Any] = field(default_factory=dict)

    uc322_conflict_detected: bool = False
    uc322_conflict_details: Dict[str, Any] = field(default_factory=dict)

    uc329_graph_paths: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    timestamp: float = field(default_factory=time.time)
    source_agent: str = "uc315"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "trace_id": self.trace_id,
            "context": self.context,
            "ai_suggestion": self.ai_suggestion,
            "ai_confidence": self.ai_confidence,
            "ai_reasoning_steps": [s.to_dict() if isinstance(s, ReasoningStep) else s for s in self.ai_reasoning_steps],
            "uc087_integrity_passed": self.uc087_integrity_passed,
            "uc087_integrity_details": self.uc087_integrity_details,
            "uc162_llmops_passed": self.uc162_llmops_passed,
            "uc162_llmops_details": self.uc162_llmops_details,
            "uc325_reflection_score": self.uc325_reflection_score,
            "uc325_reflection_details": self.uc325_reflection_details,
            "uc322_conflict_detected": self.uc322_conflict_detected,
            "uc322_conflict_details": self.uc322_conflict_details,
            "uc329_graph_paths": self.uc329_graph_paths,
            "timestamp": self.timestamp,
            "source_agent": self.source_agent,
        }


# ---------------------------------------------------------------------------
# Evaluación de riesgo
# ---------------------------------------------------------------------------

@dataclass
class RiskAssessment:
    """Resultado de la evaluación de riesgo."""
    risk_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.NONE
    confidence_score: float = 0.0
    factors: List[Dict[str, Any]] = field(default_factory=list)
    volatility: float = 0.0
    requires_escalation: bool = False
    escalation_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value if isinstance(self.risk_level, RiskLevel) else self.risk_level,
            "confidence_score": self.confidence_score,
            "factors": self.factors,
            "volatility": self.volatility,
            "requires_escalation": self.requires_escalation,
            "escalation_reasons": self.escalation_reasons,
        }


# ---------------------------------------------------------------------------
# Expediente de Decisión
# ---------------------------------------------------------------------------

@dataclass
class DecisionDossier:
    """
    Expediente de Decisión — el artefacto central del HITL.

    Contiene:
    - Datos procesados (validados por UC-087 + UC-162).
    - Razonamiento paso a paso (de UC-329 GraphRAG-GoT).
    - Auto-evaluación de calidad (de UC-325).
    - Conflicto detectado (de UC-322, si aplica).
    - Score de confianza (calculado).
    - Nivel de riesgo (calculado).
    - Sugerencia de acción.
    - Estado: [auto_execute | escalate_to_human].
    """
    dossier_id: str = ""
    trace_id: str = ""
    timestamp: float = field(default_factory=time.time)

    # Datos
    decision_input: Optional[DecisionInput] = None

    # Razonamiento
    reasoning_steps: List[ReasoningStep] = field(default_factory=list)

    # Evaluación
    risk_assessment: Optional[RiskAssessment] = None

    # Sugerencia
    ai_suggestion: str = ""
    ai_confidence: float = 0.0

    # Estado
    status: DossierStatus = DossierStatus.DRAFT
    decision: HITLDecision = HITLDecision.AUTO_EXECUTE

    # Revisión humana
    human_review: Optional[Dict[str, Any]] = None

    # Hash de integridad
    content_hash: str = ""

    # Metadata
    expires_at: float = 0.0

    def compute_hash(self) -> str:
        """Calcula hash SHA-256 del contenido del expediente."""
        payload = json.dumps({
            "dossier_id": self.dossier_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "decision_input": self.decision_input.to_dict() if self.decision_input else {},
            "reasoning_steps": [s.to_dict() for s in self.reasoning_steps],
            "risk_assessment": self.risk_assessment.to_dict() if self.risk_assessment else {},
            "ai_suggestion": self.ai_suggestion,
            "ai_confidence": self.ai_confidence,
            "status": self.status.value if isinstance(self.status, DossierStatus) else self.status,
            "decision": self.decision.value if isinstance(self.decision, HITLDecision) else self.decision,
        }, sort_keys=True, default=str)
        self.content_hash = hashlib.sha256(payload.encode()).hexdigest()
        return self.content_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dossier_id": self.dossier_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "decision_input": self.decision_input.to_dict() if self.decision_input else {},
            "reasoning_steps": [s.to_dict() for s in self.reasoning_steps],
            "risk_assessment": self.risk_assessment.to_dict() if self.risk_assessment else {},
            "ai_suggestion": self.ai_suggestion,
            "ai_confidence": self.ai_confidence,
            "status": self.status.value if isinstance(self.status, DossierStatus) else self.status,
            "decision": self.decision.value if isinstance(self.decision, HITLDecision) else self.decision,
            "human_review": self.human_review,
            "content_hash": self.content_hash,
            "expires_at": self.expires_at,
        }


# ---------------------------------------------------------------------------
# Revisión humana
# ---------------------------------------------------------------------------

@dataclass
class HumanReview:
    """Resultado de la revisión humana de un expediente."""
    reviewer_id: str = ""
    action: HumanAction = HumanAction.APPROVE
    modified_suggestion: str = ""
    override_reason: str = ""
    review_notes: str = ""
    timestamp: float = field(default_factory=time.time)
    review_duration_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reviewer_id": self.reviewer_id,
            "action": self.action.value if isinstance(self.action, HumanAction) else self.action,
            "modified_suggestion": self.modified_suggestion,
            "override_reason": self.override_reason,
            "review_notes": self.review_notes,
            "timestamp": self.timestamp,
            "review_duration_sec": self.review_duration_sec,
        }


# ---------------------------------------------------------------------------
# Resultado del pipeline HITL
# ---------------------------------------------------------------------------

@dataclass
class HITLResult:
    """Resultado completo del pipeline HITL."""
    trace_id: str = ""
    dossier_id: str = ""
    timestamp: float = field(default_factory=time.time)

    # Decisión
    decision: HITLDecision = HITLDecision.AUTO_EXECUTE
    final_action: str = ""  # la acción final a ejecutar

    # Expediente
    dossier: Optional[Dict[str, Any]] = None

    # Riesgo
    risk_level: str = "none"
    risk_score: float = 0.0
    confidence_score: float = 0.0

    # Escalamiento
    escalated: bool = False
    escalation_reasons: List[str] = field(default_factory=list)

    # Revisión humana
    human_review: Optional[Dict[str, Any]] = None

    # Issues
    issues: List[str] = field(default_factory=list)

    # Performance
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "dossier_id": self.dossier_id,
            "timestamp": self.timestamp,
            "decision": self.decision.value if isinstance(self.decision, HITLDecision) else self.decision,
            "final_action": self.final_action,
            "dossier": self.dossier,
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "confidence_score": self.confidence_score,
            "escalated": self.escalated,
            "escalation_reasons": self.escalation_reasons,
            "human_review": self.human_review,
            "issues": self.issues,
            "duration_ms": self.duration_ms,
        }


# ---------------------------------------------------------------------------
# Entrada de auditoría
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    """Entrada en el trail de auditoría."""
    entry_id: str = ""
    dossier_id: str = ""
    trace_id: str = ""
    timestamp: float = field(default_factory=time.time)
    event: str = ""
    actor: str = ""  # "ai", "human", "system"
    details: Dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "dossier_id": self.dossier_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "event": self.event,
            "actor": self.actor,
            "details": self.details,
            "content_hash": self.content_hash,
        }


def generate_id() -> str:
    """Genera un UUID único."""
    return str(uuid.uuid4())
