"""
UC-087 — Modelos de datos para MLSecOps / Defense in Depth.

Define configuración, resultados de validación, reportes de robustez,
versiones de modelo y decisiones del guardian.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
import time
import uuid


class ThreatCategory(Enum):
    DATA_POISONING = "data_poisoning"
    BACKDOOR = "backdoor"
    ADVERSARIAL_EXAMPLE = "adversarial_example"
    MODEL_MANIPULATION = "model_manipulation"
    ARTIFACT_TAMPERING = "artifact_tampering"
    UNKNOWN = "unknown"


class DefenseAction(Enum):
    ALLOW = "allow"
    SANITIZE = "sanitize"
    QUARANTINE = "quarantine"
    ROLLBACK = "rollback"
    ESCALATE = "escalate"


class ModelPromotion(Enum):
    PROMOTE = "promote"
    REJECT = "reject"
    CANARY = "canary"


@dataclass
class MLSecOpsConfig:
    """Configuración de la capa de seguridad ML."""
    hash_algorithm: str = "sha256"
    outlier_threshold: float = 3.0
    feature_squeeze_epsilon: float = 0.01
    adversarial_epsilon: float = 0.05
    adversarial_steps: int = 10
    robustness_gap_threshold: float = 0.15
    slice_drop_threshold: float = 0.30
    entropy_anomaly_zscore: float = 2.0
    min_samples_for_training: int = 50
    canary_traffic_ratio: float = 0.1
    max_failed_retrain_attempts: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hash_algorithm": self.hash_algorithm,
            "outlier_threshold": self.outlier_threshold,
            "feature_squeeze_epsilon": self.feature_squeeze_epsilon,
            "adversarial_epsilon": self.adversarial_epsilon,
            "adversarial_steps": self.adversarial_steps,
            "robustness_gap_threshold": self.robustness_gap_threshold,
            "slice_drop_threshold": self.slice_drop_threshold,
            "entropy_anomaly_zscore": self.entropy_anomaly_zscore,
            "min_samples_for_training": self.min_samples_for_training,
            "canary_traffic_ratio": self.canary_traffic_ratio,
            "max_failed_retrain_attempts": self.max_failed_retrain_attempts,
        }


@dataclass
class DataPoint:
    """Observación o fila de datos tabular."""
    features: List[float]
    label: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "features": self.features,
            "label": self.label,
            "metadata": self.metadata,
        }


@dataclass
class ProvenanceCheck:
    """Resultado de validación de provenance."""
    check_name: str
    passed: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class ValidationReport:
    """Reporte de validación de un batch de entrenamiento."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    all_passed: bool = False
    provenance_checks: List[ProvenanceCheck] = field(default_factory=list)
    outlier_dropped: int = 0
    squeezed_differences: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "all_passed": self.all_passed,
            "provenance_checks": [c.to_dict() for c in self.provenance_checks],
            "outlier_dropped": self.outlier_dropped,
            "squeezed_differences": self.squeezed_differences,
            "timestamp": self.timestamp,
        }


@dataclass
class RobustnessReport:
    """Resultado de evaluación de robustez adversaria."""
    clean_accuracy: float = 0.0
    adversarial_accuracy: float = 0.0
    robustness_gap: float = 0.0
    passed: bool = False
    attack_type: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clean_accuracy": round(self.clean_accuracy, 4),
            "adversarial_accuracy": round(self.adversarial_accuracy, 4),
            "robustness_gap": round(self.robustness_gap, 4),
            "passed": self.passed,
            "attack_type": self.attack_type,
            "details": self.details,
        }


@dataclass
class SliceAlert:
    """Alerta de caída de performance en un slice."""
    slice_name: str
    baseline_accuracy: float = 0.0
    current_accuracy: float = 0.0
    drop: float = 0.0
    severity: str = "P1"
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slice_name": self.slice_name,
            "baseline_accuracy": round(self.baseline_accuracy, 4),
            "current_accuracy": round(self.current_accuracy, 4),
            "drop": round(self.drop, 4),
            "severity": self.severity,
            "description": self.description,
        }


@dataclass
class TriggerReport:
    """Reporte de detección de triggers/backdoors."""
    entropy_alert: bool = False
    entropy_zscore: float = 0.0
    slice_alerts: List[SliceAlert] = field(default_factory=list)
    suspicious_features: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entropy_alert": self.entropy_alert,
            "entropy_zscore": round(self.entropy_zscore, 4),
            "slice_alerts": [a.to_dict() for a in self.slice_alerts],
            "suspicious_features": self.suspicious_features,
        }


@dataclass
class ModelVersion:
    """Versión de modelo guardada para rollback."""
    version_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: float = field(default_factory=time.time)
    path: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    is_canary: bool = False
    promoted: bool = False
    rejected: bool = False
    rejection_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "timestamp": self.timestamp,
            "path": self.path,
            "metrics": self.metrics,
            "is_canary": self.is_canary,
            "promoted": self.promoted,
            "rejected": self.rejected,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class SecurityDecision:
    """Decisión del guardian de seguridad ML."""
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    action: DefenseAction = DefenseAction.ALLOW
    promotion: ModelPromotion = ModelPromotion.REJECT
    threat_categories: List[ThreatCategory] = field(default_factory=list)
    justification: str = ""
    validation_report: Optional[ValidationReport] = None
    robustness_report: Optional[RobustnessReport] = None
    trigger_report: Optional[TriggerReport] = None
    model_version: Optional[ModelVersion] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "action": self.action.value,
            "promotion": self.promotion.value,
            "threat_categories": [t.value for t in self.threat_categories],
            "justification": self.justification,
            "validation_report": self.validation_report.to_dict() if self.validation_report else None,
            "robustness_report": self.robustness_report.to_dict() if self.robustness_report else None,
            "trigger_report": self.trigger_report.to_dict() if self.trigger_report else None,
            "model_version": self.model_version.to_dict() if self.model_version else None,
            "timestamp": self.timestamp,
        }


@dataclass
class MLSecOpsResult:
    """Resultado completo de una ejecución del guardian."""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision: Optional[SecurityDecision] = None
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "decision": self.decision.to_dict() if self.decision else None,
            "alerts": self.alerts,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp,
        }
