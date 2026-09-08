"""UC-087 — Bucle de retroalimentación HITL para MLOps.

Consume decisiones aprobadas/modificadas por revisores humanos (UC-290),
las convierte en ejemplos de entrenamiento validados y, cuando se acumulan
suficientes, dispara un reentrenamiento supervisado via
MLOpsSelfHealingOrchestrator. Todo se audita en UC-309.

Principios:
1. Solo decisiones APPROVED o MODIFIED por humanos entran al bucle.
2. El revisor es el label; la sugerencia modificada es el target.
3. El reentrenamiento requiere umbral mínimo de ejemplos.
4. UC-087/UC-087 valida y guarda candidato; promoción sigue requiriendo HITL.
5. UC-309 recibe eventos de cada paso para trazabilidad.
6. Políticas regulatorias por dominio (healthcare, finance, criminal_justice)
   controlan features prohibidas, retención y umbrales de auto-aprobación.
7. Ambiguity score (confianza + concentración de features) determina riesgo.
8. Validación de dataset verifica diversidad de revisores, temporal y features
   prohibidas antes de permitir reentrenamiento.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from models_087 import DataPoint


# ---------------------------------------------------------------------------
# Políticas regulatorias por dominio
# ---------------------------------------------------------------------------

DOMAIN_POLICIES: Dict[str, Dict[str, Any]] = {
    "healthcare": {
        "requires_explanation": True,
        "requires_consent": True,
        "prohibited_features": ["race", "ethnicity", "insurance_status"],
        "min_confidence_for_auto": 0.95,
        "retention_years": 7,
        "compliance": ["gdpr", "hipaa"],
    },
    "finance": {
        "requires_explanation": True,
        "requires_audit_trail": True,
        "prohibited_features": ["gender", "age", "national_origin"],
        "min_confidence_for_auto": 0.90,
        "retention_years": 5,
        "compliance": ["gdpr", "sox"],
    },
    "criminal_justice": {
        "requires_human_review": True,
        "requires_explanation": True,
        "prohibited_features": ["race", "gender", "zip_code"],
        "min_confidence_for_auto": 1.0,  # Nunca auto-aprobar
        "retention_years": 10,
        "compliance": ["gdpr", "constitutional_review"],
    },
    "default": {
        "requires_explanation": False,
        "prohibited_features": [],
        "min_confidence_for_auto": 0.85,
        "retention_years": 5,
        "compliance": [],
    },
}


@dataclass
class RegulatoryPolicy:
    """Política regulatoria configurable por dominio."""
    domain: str = "default"
    prohibited_features: List[str] = field(default_factory=list)
    min_confidence_for_auto: float = 0.85
    retention_years: int = 5
    requires_human_review: bool = False
    requires_explanation: bool = False
    compliance: List[str] = field(default_factory=list)

    @classmethod
    def for_domain(cls, domain: str) -> "RegulatoryPolicy":
        p = DOMAIN_POLICIES.get(domain, DOMAIN_POLICIES["default"])
        return cls(
            domain=domain,
            prohibited_features=list(p.get("prohibited_features", [])),
            min_confidence_for_auto=p.get("min_confidence_for_auto", 0.85),
            retention_years=p.get("retention_years", 5),
            requires_human_review=p.get("requires_human_review", False),
            requires_explanation=p.get("requires_explanation", False),
            compliance=list(p.get("compliance", [])),
        )

    def is_feature_prohibited(self, feature_name: str) -> bool:
        return feature_name.lower() in [f.lower() for f in self.prohibited_features]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "prohibited_features": self.prohibited_features,
            "min_confidence_for_auto": self.min_confidence_for_auto,
            "retention_years": self.retention_years,
            "requires_human_review": self.requires_human_review,
            "requires_explanation": self.requires_explanation,
            "compliance": self.compliance,
        }


# ---------------------------------------------------------------------------
# Ambiguity score
# ---------------------------------------------------------------------------

def compute_ambiguity_score(
    confidence_score: float,
    feature_importance: Optional[Dict[str, float]] = None,
) -> float:
    """Calcula un score de ambigüedad [0,1].

    Valores cercanos a 1.0 indican alta ambigüedad (requiere revisión humana).
    Combina confianza del modelo y concentración de feature importance.
    """
    confidence_ambiguity = 1.0 - confidence_score

    if feature_importance:
        values = list(feature_importance.values())
        if values:
            max_importance = max(values)
            feature_concentration = max_importance / (sum(values) + 1e-10)
            feature_ambiguity = 1.0 - feature_concentration
        else:
            feature_ambiguity = 0.5
    else:
        feature_ambiguity = 0.5

    return min(1.0, max(0.0, 0.6 * confidence_ambiguity + 0.4 * feature_ambiguity))


# ---------------------------------------------------------------------------
# Validación de dataset
# ---------------------------------------------------------------------------

@dataclass
class DatasetValidationResult:
    """Resultado de validación de dataset de reentrenamiento."""
    compliant: bool
    violations: List[str] = field(default_factory=list)
    dataset_size: int = 0
    unique_reviewers: int = 0
    temporal_span_days: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "compliant": self.compliant,
            "violations": self.violations,
            "dataset_size": self.dataset_size,
            "unique_reviewers": self.unique_reviewers,
            "temporal_span_days": self.temporal_span_days,
        }


def validate_training_dataset(
    examples: List["FeedbackExample"],
    policy: RegulatoryPolicy,
    min_reviewers: int = 2,
    min_temporal_span_days: float = 1.0,
) -> DatasetValidationResult:
    """Valida que el dataset cumple requisitos regulatorios antes de reentrenar.

    Verifica:
    1. Diversidad de revisores (evitar sesgo de un solo revisor).
    2. Distribución temporal (evitar sesgo temporal).
    3. Ausencia de features prohibidas en metadatos.
    """
    violations: List[str] = []

    reviewers = set(ex.reviewer_id for ex in examples)
    if len(reviewers) < min_reviewers:
        violations.append("insufficient_reviewer_diversity")

    timestamps = [ex.timestamp for ex in examples]
    if timestamps:
        time_span = max(timestamps) - min(timestamps)
        span_days = time_span / 86400.0
        if span_days < min_temporal_span_days:
            violations.append("insufficient_temporal_diversity")
    else:
        span_days = 0.0

    for ex in examples:
        for feature in (ex.reason or "").lower().split():
            if policy.is_feature_prohibited(feature):
                violations.append(f"prohibited_feature_in_training:{feature}")

    return DatasetValidationResult(
        compliant=len(violations) == 0,
        violations=violations,
        dataset_size=len(examples),
        unique_reviewers=len(reviewers),
        temporal_span_days=span_days,
    )


@dataclass
class FeedbackExample:
    """Ejemplo de entrenamiento derivado de una revisión humana."""
    example_id: str
    trace_id: str
    dossier_id: str
    reviewer_id: str
    input_features: List[float]
    label: int
    target_action: str
    reason: str
    timestamp: float
    approved: bool
    confidence_score: float = 0.0
    feature_importance: Dict[str, float] = field(default_factory=dict)
    ambiguity_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "example_id": self.example_id,
            "trace_id": self.trace_id,
            "dossier_id": self.dossier_id,
            "reviewer_id": self.reviewer_id,
            "input_features": self.input_features,
            "label": self.label,
            "target_action": self.target_action,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "approved": self.approved,
            "confidence_score": self.confidence_score,
            "feature_importance": self.feature_importance,
            "ambiguity_score": self.ambiguity_score,
        }

    def to_data_point(self) -> DataPoint:
        return DataPoint(
            features=self.input_features,
            label=self.label,
            metadata={
                "trace_id": self.trace_id,
                "dossier_id": self.dossier_id,
                "reviewer_id": self.reviewer_id,
                "target_action": self.target_action,
                "reason": self.reason,
                "source": "hitl_feedback",
                "ambiguity_score": self.ambiguity_score,
            },
        )


@dataclass
class HITLDecisionInput:
    """Decisión HITL genérica que consume el bucle."""
    trace_id: str
    dossier_id: str
    decision: str  # approved, modified, rejected, etc.
    reviewer_id: str
    final_action: str
    ai_suggestion: str
    modified_suggestion: Optional[str]
    review_notes: str
    input_context: Dict[str, Any]
    timestamp: float
    confidence_score: float = 0.0
    feature_importance: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "dossier_id": self.dossier_id,
            "decision": self.decision,
            "reviewer_id": self.reviewer_id,
            "final_action": self.final_action,
            "ai_suggestion": self.ai_suggestion,
            "modified_suggestion": self.modified_suggestion,
            "review_notes": self.review_notes,
            "input_context": self.input_context,
            "timestamp": self.timestamp,
            "confidence_score": self.confidence_score,
            "feature_importance": self.feature_importance,
        }


class MLOpsHITLFeedbackLoop:
    """Bucle cerrado: HITL → ejemplos → reentrenamiento → auditoría."""

    def __init__(
        self,
        self_healing_orchestrator: Any,
        min_examples_for_retrain: int = 10,
        event_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
        domain: str = "default",
        policy: Optional[RegulatoryPolicy] = None,
        min_reviewers_for_retrain: int = 2,
        min_temporal_span_days: float = 1.0,
    ) -> None:
        self.orchestrator = self_healing_orchestrator
        self.min_examples = min_examples_for_retrain
        self.event_sink = event_sink
        self.policy = policy or RegulatoryPolicy.for_domain(domain)
        self.min_reviewers = min_reviewers_for_retrain
        self.min_temporal_span_days = min_temporal_span_days
        self._examples: List[FeedbackExample] = []
        self._retrain_history: List[Dict[str, Any]] = []
        self._validation_history: List[Dict[str, Any]] = []

    def _emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self.event_sink is not None:
            try:
                self.event_sink({"event_type": event_type, "timestamp": time.time(), **payload})
            except Exception:
                pass

    def ingest_decision(self, decision: HITLDecisionInput) -> Optional[FeedbackExample]:
        """Consume una decisión HITL y genera un ejemplo si aplica."""
        if decision.decision not in ("approved", "modified"):
            self._emit("hitl_decision_skipped", decision.to_dict())
            return None

        # Verificar features prohibidas en el contexto de entrada
        for feature_key in decision.input_context.keys():
            if self.policy.is_feature_prohibited(feature_key):
                self._emit("hitl_decision_blocked", {
                    **decision.to_dict(),
                    "reason": f"prohibited_feature:{feature_key}",
                })
                return None

        # Extraer features del contexto; fallback a vector vacío
        features = decision.input_context.get("features", [])
        if not features or not all(isinstance(x, (int, float)) for x in features):
            self._emit("hitl_decision_skipped", {**decision.to_dict(), "reason": "no_numeric_features"})
            return None

        target_action = decision.modified_suggestion or decision.final_action or decision.ai_suggestion
        # Label binario simplificado: 1 si aprobó/modificó hacia BUY/uptrend, 0 hacia SELL/downtrend
        label = 1 if any(w in target_action.lower() for w in ("buy", "approve", "yes", "true")) else 0

        ambiguity = compute_ambiguity_score(
            decision.confidence_score,
            decision.feature_importance,
        )

        example = FeedbackExample(
            example_id=str(uuid.uuid4())[:12],
            trace_id=decision.trace_id,
            dossier_id=decision.dossier_id,
            reviewer_id=decision.reviewer_id,
            input_features=[float(x) for x in features],
            label=label,
            target_action=target_action,
            reason=decision.review_notes,
            timestamp=time.time(),
            approved=True,
            confidence_score=decision.confidence_score,
            feature_importance=decision.feature_importance,
            ambiguity_score=ambiguity,
        )

        self._examples.append(example)
        self._emit("hitl_feedback_example_created", example.to_dict())
        return example

    def collect_examples(self, min_count: Optional[int] = None) -> List[DataPoint]:
        """Devuelve ejemplos acumulados como DataPoints."""
        count = min_count or self.min_examples
        return [ex.to_data_point() for ex in self._examples[-count:]]

    def should_retrain(self) -> bool:
        """Indica si hay suficientes ejemplos para reentrenar."""
        return len(self._examples) >= self.min_examples

    def maybe_retrain(
        self,
        agent_id: str,
        force: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Si hay suficientes ejemplos, dispara reentrenamiento supervisado.

        Valida el dataset contra políticas regulatorias antes de reentrenar.
        """
        if not force and not self.should_retrain():
            return None

        data = self.collect_examples()
        if not data:
            return None

        # Validar dataset contra políticas regulatorias
        validation = validate_training_dataset(
            self._examples[-len(data):],
            self.policy,
            min_reviewers=self.min_reviewers,
            min_temporal_span_days=self.min_temporal_span_days,
        )
        self._validation_history.append(validation.to_dict())

        if not validation.compliant:
            self._emit("hitl_retrain_blocked_validation", {
                "agent_id": agent_id,
                "example_count": len(data),
                "violations": validation.violations,
            })
            return {
                "status": "blocked",
                "reason": "dataset_validation_failed",
                "violations": validation.violations,
                "validation": validation.to_dict(),
            }

        self._emit("hitl_retrain_started", {
            "agent_id": agent_id,
            "example_count": len(data),
            "example_ids": [e.to_dict()["example_id"] for e in self._examples[-len(data):]],
            "validation": validation.to_dict(),
        })

        result = self.orchestrator.retrain(data, agent_id)

        if result is not None:
            self._retrain_history.append({
                "timestamp": time.time(),
                "agent_id": agent_id,
                "example_count": len(data),
                "version_id": result.get("version_id"),
                "validation": validation.to_dict(),
            })
            self._emit("hitl_retrain_completed", {
                "agent_id": agent_id,
                "example_count": len(data),
                "version_id": result.get("version_id"),
            })
            # Limpia ejemplos consumidos para no repetirlos
            self._examples = self._examples[:-len(data)]
        else:
            self._emit("hitl_retrain_failed", {
                "agent_id": agent_id,
                "example_count": len(data),
            })

        return result

    def get_examples(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._examples]

    def get_retrain_history(self) -> List[Dict[str, Any]]:
        return self._retrain_history

    def get_validation_history(self) -> List[Dict[str, Any]]:
        return self._validation_history

    def get_policy(self) -> Dict[str, Any]:
        return self.policy.to_dict()
