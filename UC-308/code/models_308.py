"""
UC-308 — Modelos de datos para Agent Drift / Environmental Degradation.

Define enumeraciones, configuración, casos golden, resultados de ejecución,
baselines, señales de deriva, alertas y recomendaciones.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class DriftType(str, Enum):
    """Tipos de deriva detectables."""
    CONTRACT_API = "contract_api"
    HTML_INTERFACE = "html_interface"
    DATA_DISTRIBUTION = "data_distribution"
    TOOL_OPERATIONAL = "tool_operational"
    BEHAVIORAL = "behavioral"
    QUALITY = "quality"


class DriftStatus(str, Enum):
    """Estado de una señal de deriva individual o de una evaluación."""
    NORMAL = "normal"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class SystemStatus(str, Enum):
    """Estado global del sistema."""
    NORMAL = "normal"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class RecommendationAction(str, Enum):
    """Tipos de recomendación de mitigación. Nunca implican auto-modificación."""
    ALERT_TEAM = "alert_team"
    INCREASE_HITL_UC290 = "increase_hitl_uc290"
    DISABLE_TOOL_UC300 = "disable_tool_uc300"
    CONTAINMENT_ROLLBACK_UC324 = "containment_rollback_uc324"


@dataclass
class GoldenCase:
    """Caso de referencia del golden dataset."""
    id: str
    name: str
    description: str
    tool: str
    environment: str
    agent_version: str
    input_payload: Dict[str, Any] = field(default_factory=dict)
    expected_schema_keys: Optional[List[str]] = None
    expected_html_selectors: Optional[List[str]] = None
    expected_output: Any = None
    distribution_config: Optional[Dict[str, Any]] = None
    secret: bool = False
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_secret: bool = False) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tool": self.tool,
            "environment": self.environment,
            "agent_version": self.agent_version,
            "input_payload": self.input_payload,
            "expected_schema_keys": self.expected_schema_keys,
            "expected_html_selectors": self.expected_html_selectors,
            "expected_output": self.expected_output,
            "distribution_config": self.distribution_config,
            "secret": self.secret,
            "tags": self.tags,
            "metadata": self.metadata,
        }
        if not include_secret:
            d.pop("expected_output", None)
            d.pop("input_payload", None)
            d.pop("distribution_config", None)
        return d


@dataclass
class DatasetSignature:
    """Firma/hash de un golden dataset."""
    algorithm: str = "sha256"
    content_hash: str = ""
    hmac_signature: str = ""
    signed_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "content_hash": self.content_hash,
            "hmac_signature": self.hmac_signature,
            "signed_at": self.signed_at,
        }


@dataclass
class GoldenDataset:
    """Conjunto de referencia versionado, hasheado y firmado."""
    version: str
    cases: List[GoldenCase]
    public_case_ids: List[str] = field(default_factory=list)
    secret_case_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    signature: DatasetSignature = field(default_factory=DatasetSignature)

    def __post_init__(self):
        if not self.public_case_ids:
            self.public_case_ids = [c.id for c in self.cases if not c.secret]
        if not self.secret_case_ids:
            self.secret_case_ids = [c.id for c in self.cases if c.secret]

    def canonical_content(self) -> str:
        """Representación canónica usada para hash/HMAC."""
        cases = []
        for case in sorted(self.cases, key=lambda c: c.id):
            cases.append({
                "id": case.id,
                "name": case.name,
                "tool": case.tool,
                "environment": case.environment,
                "agent_version": case.agent_version,
                "input_payload": case.input_payload,
                "expected_schema_keys": case.expected_schema_keys,
                "expected_html_selectors": case.expected_html_selectors,
                "expected_output": case.expected_output,
                "distribution_config": case.distribution_config,
                "secret": case.secret,
                "tags": sorted(case.tags),
                "metadata": case.metadata,
            })
        payload = {
            "version": self.version,
            "created_at": self.created_at,
            "cases": cases,
            "public_case_ids": sorted(self.public_case_ids),
            "secret_case_ids": sorted(self.secret_case_ids),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)

    def compute_hash(self) -> str:
        return hashlib.sha256(self.canonical_content().encode("utf-8")).hexdigest()

    def sign(self, secret_key: str) -> DatasetSignature:
        content = self.canonical_content()
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        sig = hmac.new(
            secret_key.encode("utf-8"),
            content_hash.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        self.signature = DatasetSignature(
            algorithm="sha256",
            content_hash=content_hash,
            hmac_signature=sig,
            signed_at=time.time(),
        )
        return self.signature

    def verify_signature(self, secret_key: str) -> bool:
        if not self.signature or not self.signature.hmac_signature:
            return False
        expected = hmac.new(
            secret_key.encode("utf-8"),
            self.signature.content_hash.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, self.signature.hmac_signature)

    def verify_integrity(self) -> bool:
        if not self.signature or not self.signature.content_hash:
            return False
        return self.compute_hash() == self.signature.content_hash

    def to_dict(self, include_secret: bool = False) -> Dict[str, Any]:
        public = [c.to_dict(include_secret=False) for c in self.cases if not c.secret]
        secret_meta = [c.to_dict(include_secret=False) for c in self.cases if c.secret]
        return {
            "version": self.version,
            "created_at": self.created_at,
            "case_count": len(self.cases),
            "public_case_count": len(self.public_case_ids),
            "secret_case_count": len(self.secret_case_ids),
            "signature": self.signature.to_dict(),
            "public_cases": public if include_secret or True else [],
            "secret_cases_metadata": secret_meta if include_secret else [],
        }


@dataclass
class AgentResult:
    """Resultado de ejecutar un caso golden contra el entorno simulado."""
    case_id: str
    tool: str
    environment: str
    agent_version: str
    trace_id: str = ""
    success: bool = False
    status: str = "unknown"
    latency_ms: float = 0.0
    tokens: float = 0.0
    output: Any = None
    error: str = ""
    schema_fingerprint: str = ""
    html_fingerprint: str = ""
    quality_score: float = 0.0
    steps: int = 0
    retries: int = 0
    escalations: int = 0
    uc300_blocks: int = 0
    uc290_overrides: int = 0
    timeout: bool = False
    resource_usage: Dict[str, float] = field(default_factory=dict)
    data_samples: Optional[List[float]] = None
    category_counts: Optional[Dict[str, int]] = None
    distribution_params: Optional[Dict[str, Any]] = None
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "tool": self.tool,
            "environment": self.environment,
            "agent_version": self.agent_version,
            "trace_id": self.trace_id,
            "success": self.success,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "tokens": self.tokens,
            "output": self.output,
            "error": self.error,
            "schema_fingerprint": self.schema_fingerprint,
            "html_fingerprint": self.html_fingerprint,
            "quality_score": self.quality_score,
            "steps": self.steps,
            "retries": self.retries,
            "escalations": self.escalations,
            "uc300_blocks": self.uc300_blocks,
            "uc290_overrides": self.uc290_overrides,
            "timeout": self.timeout,
            "resource_usage": self.resource_usage,
            "data_samples": self.data_samples,
            "category_counts": self.category_counts,
            "distribution_params": self.distribution_params,
            "evidence": self.evidence,
        }


@dataclass
class BaselineMetrics:
    """Métricas base contra las que comparar."""
    success_rate: float = 1.0
    quality_score: float = 1.0
    latency_ms_mean: float = 0.0
    latency_ms_p95: float = 0.0
    tokens_mean: float = 0.0
    error_rate: float = 0.0
    timeout_rate: float = 0.0
    resource_mean: Dict[str, float] = field(default_factory=dict)
    schema_fingerprint: str = ""
    schema_fingerprints: List[str] = field(default_factory=list)
    html_selector_fingerprint: str = ""
    html_selector_fingerprints: List[str] = field(default_factory=list)
    distribution: Dict[str, Any] = field(default_factory=dict)
    behavior: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success_rate": self.success_rate,
            "quality_score": self.quality_score,
            "latency_ms_mean": self.latency_ms_mean,
            "latency_ms_p95": self.latency_ms_p95,
            "tokens_mean": self.tokens_mean,
            "error_rate": self.error_rate,
            "timeout_rate": self.timeout_rate,
            "resource_mean": self.resource_mean,
            "schema_fingerprint": self.schema_fingerprint,
            "schema_fingerprints": self.schema_fingerprints,
            "html_selector_fingerprint": self.html_selector_fingerprint,
            "html_selector_fingerprints": self.html_selector_fingerprints,
            "distribution": self.distribution,
            "behavior": self.behavior,
        }


@dataclass
class Baseline:
    """Baseline por agente, herramienta, entorno y versión."""
    baseline_id: str
    agent_id: str
    tool: str
    environment: str
    agent_version: str
    created_at: float
    source_run_id: str
    metrics: BaselineMetrics = field(default_factory=BaselineMetrics)
    thresholds: Dict[str, Any] = field(default_factory=dict)

    def key(self) -> Tuple[str, str, str, str]:
        return (self.agent_id, self.tool, self.environment, self.agent_version)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "agent_id": self.agent_id,
            "tool": self.tool,
            "environment": self.environment,
            "agent_version": self.agent_version,
            "created_at": self.created_at,
            "source_run_id": self.source_run_id,
            "metrics": self.metrics.to_dict(),
            "thresholds": self.thresholds,
        }


@dataclass
class DriftSignal:
    """Señal de deriva detectada en una evaluación."""
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = ""
    drift_type: DriftType = DriftType.QUALITY
    tool: str = ""
    status: DriftStatus = DriftStatus.NORMAL
    score: float = 0.0
    absolute_delta: float = 0.0
    relative_delta: float = 0.0
    baseline_id: str = ""
    dimension: str = ""
    message: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "run_id": self.run_id,
            "drift_type": self.drift_type.value,
            "tool": self.tool,
            "status": self.status.value,
            "score": self.score,
            "absolute_delta": self.absolute_delta,
            "relative_delta": self.relative_delta,
            "baseline_id": self.baseline_id,
            "dimension": self.dimension,
            "message": self.message,
            "evidence": self.evidence,
        }


@dataclass
class Recommendation:
    """Recomendación de mitigación sin auto-modificación."""
    action: RecommendationAction
    target_tool: str
    reason: str
    auto_apply: bool = False
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "target_tool": self.target_tool,
            "reason": self.reason,
            "auto_apply": self.auto_apply,
            "evidence": self.evidence,
        }


@dataclass
class Alert:
    """Alerta emitida por el sistema."""
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    run_id: str = ""
    status: DriftStatus = DriftStatus.WARNING
    drift_signal_ids: List[str] = field(default_factory=list)
    system_status: SystemStatus = SystemStatus.NORMAL
    recommendations: List[Recommendation] = field(default_factory=list)
    acknowledged: bool = False
    resolved: bool = False
    resolved_at: float = 0.0
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "timestamp": self.timestamp,
            "run_id": self.run_id,
            "status": self.status.value,
            "drift_signal_ids": self.drift_signal_ids,
            "system_status": self.system_status.value,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at,
            "message": self.message,
        }


@dataclass
class EvaluationRun:
    """Ejecución de una evaluación del golden dataset."""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    trigger: str = "manual"
    dataset_version: str = ""
    dataset_hash: str = ""
    agent_id: str = ""
    environment: str = ""
    agent_version: str = ""
    results: List[AgentResult] = field(default_factory=list)
    aggregate: Dict[str, Any] = field(default_factory=dict)
    drift_signals: List[DriftSignal] = field(default_factory=list)
    system_status: SystemStatus = SystemStatus.NORMAL
    alert_ids: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "trigger": self.trigger,
            "dataset_version": self.dataset_version,
            "dataset_hash": self.dataset_hash,
            "agent_id": self.agent_id,
            "environment": self.environment,
            "agent_version": self.agent_version,
            "results": [r.to_dict() for r in self.results],
            "aggregate": self.aggregate,
            "drift_signals": [s.to_dict() for s in self.drift_signals],
            "system_status": self.system_status.value,
            "alert_ids": self.alert_ids,
            "evidence": self.evidence,
            "duration_ms": self.duration_ms,
        }


@dataclass
class DriftConfig:
    """Configuración del motor de detección de deriva."""
    agent_id: str = "uc308_default_agent"
    environment: str = "default"
    agent_version: str = "1.0.0"
    success_rate_warning: float = 0.90
    success_rate_degraded: float = 0.80
    success_rate_critical: float = 0.60
    quality_score_warning: float = 0.90
    quality_score_degraded: float = 0.75
    latency_relative_warning: float = 0.50
    latency_relative_degraded: float = 1.00
    latency_relative_critical: float = 2.00
    error_rate_warning: float = 0.10
    error_rate_degraded: float = 0.20
    error_rate_critical: float = 0.40
    timeout_rate_warning: float = 0.05
    timeout_rate_degraded: float = 0.15
    resource_relative_warning: float = 1.50
    resource_relative_degraded: float = 3.00
    schema_drift_missing_keys_warning: int = 1
    schema_drift_missing_keys_degraded: int = 2
    html_selector_missing_warning: int = 1
    html_selector_missing_degraded: int = 2
    psi_warning: float = 0.20
    psi_degraded: float = 0.50
    behavioral_relative_warning: float = 0.30
    behavioral_relative_degraded: float = 0.60
    consecutive_degraded_to_alert: int = 2
    consecutive_critical_to_alert: int = 1
    consecutive_normal_to_resolve: int = 2
    window_size: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "environment": self.environment,
            "agent_version": self.agent_version,
            "success_rate_warning": self.success_rate_warning,
            "success_rate_degraded": self.success_rate_degraded,
            "success_rate_critical": self.success_rate_critical,
            "quality_score_warning": self.quality_score_warning,
            "quality_score_degraded": self.quality_score_degraded,
            "latency_relative_warning": self.latency_relative_warning,
            "latency_relative_degraded": self.latency_relative_degraded,
            "latency_relative_critical": self.latency_relative_critical,
            "error_rate_warning": self.error_rate_warning,
            "error_rate_degraded": self.error_rate_degraded,
            "error_rate_critical": self.error_rate_critical,
            "timeout_rate_warning": self.timeout_rate_warning,
            "timeout_rate_degraded": self.timeout_rate_degraded,
            "resource_relative_warning": self.resource_relative_warning,
            "resource_relative_degraded": self.resource_relative_degraded,
            "schema_drift_missing_keys_warning": self.schema_drift_missing_keys_warning,
            "schema_drift_missing_keys_degraded": self.schema_drift_missing_keys_degraded,
            "html_selector_missing_warning": self.html_selector_missing_warning,
            "html_selector_missing_degraded": self.html_selector_missing_degraded,
            "psi_warning": self.psi_warning,
            "psi_degraded": self.psi_degraded,
            "behavioral_relative_warning": self.behavioral_relative_warning,
            "behavioral_relative_degraded": self.behavioral_relative_degraded,
            "consecutive_degraded_to_alert": self.consecutive_degraded_to_alert,
            "consecutive_critical_to_alert": self.consecutive_critical_to_alert,
            "consecutive_normal_to_resolve": self.consecutive_normal_to_resolve,
            "window_size": self.window_size,
        }
