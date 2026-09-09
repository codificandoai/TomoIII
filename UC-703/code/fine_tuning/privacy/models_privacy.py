"""Modelos de dominio para Privacy-Preserving LLMOps."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DataContract:
    contract_id: str = field(default_factory=lambda: f"contract-{uuid.uuid4().hex[:8]}")
    required_fields: List[str] = field(default_factory=list)
    forbidden_fields: List[str] = field(default_factory=list)
    purpose: str = ""
    max_retention_hours: float = 168.0
    allowed_regions: List[str] = field(default_factory=lambda: ["private"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "required_fields": self.required_fields,
            "forbidden_fields": self.forbidden_fields,
            "purpose": self.purpose,
            "max_retention_hours": self.max_retention_hours,
            "allowed_regions": self.allowed_regions,
        }


@dataclass
class DeIdentificationResult:
    result_id: str = field(default_factory=lambda: f"deid-{uuid.uuid4().hex[:8]}")
    engine: str = "regex"
    findings: List[Dict[str, Any]] = field(default_factory=list)
    anonymized_text: str = ""
    method: str = "pseudonymize"  # redact, pseudonymize, tokenize
    reversible_map: Dict[str, str] = field(default_factory=dict)
    passed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "engine": self.engine,
            "findings": self.findings,
            "anonymized_text": self.anonymized_text,
            "method": self.method,
            "reversible_map": self.reversible_map,
            "passed": self.passed,
        }


@dataclass
class DataRetentionDecision:
    decision_id: str = field(default_factory=lambda: f"ret-{uuid.uuid4().hex[:8]}")
    raw_data_uri: str = ""
    action: str = "keep"  # keep, delete, archive
    reason: str = ""
    expires_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "raw_data_uri": self.raw_data_uri,
            "action": self.action,
            "reason": self.reason,
            "expires_at": self.expires_at,
        }


@dataclass
class DPTrainingConfig:
    config_id: str = field(default_factory=lambda: f"dp-{uuid.uuid4().hex[:8]}")
    enabled: bool = True
    epsilon: float = 1.0
    delta: float = 1e-5
    max_grad_norm: float = 1.0
    noise_multiplier: float = 1.0
    method: str = "dp-sgd"  # dp-sgd, dp-adam

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config_id": self.config_id,
            "enabled": self.enabled,
            "epsilon": self.epsilon,
            "delta": self.delta,
            "max_grad_norm": self.max_grad_norm,
            "noise_multiplier": self.noise_multiplier,
            "method": self.method,
        }


@dataclass
class DPTrainingResult:
    result_id: str = field(default_factory=lambda: f"dpres-{uuid.uuid4().hex[:8]}")
    run_id: str = ""
    epsilon_spent: float = 0.0
    delta_spent: float = 0.0
    privacy_budget_exceeded: bool = False
    noise_std_applied: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "run_id": self.run_id,
            "epsilon_spent": self.epsilon_spent,
            "delta_spent": self.delta_spent,
            "privacy_budget_exceeded": self.privacy_budget_exceeded,
            "noise_std_applied": self.noise_std_applied,
        }


@dataclass
class MembershipInferenceReport:
    report_id: str = field(default_factory=lambda: f"mi-{uuid.uuid4().hex[:8]}")
    run_id: str = ""
    attack_accuracy: float = 0.0
    exposure_risk: str = "low"  # low, medium, high, critical
    memorized_samples: List[Dict[str, Any]] = field(default_factory=list)
    passed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "run_id": self.run_id,
            "attack_accuracy": self.attack_accuracy,
            "exposure_risk": self.exposure_risk,
            "memorized_samples": self.memorized_samples,
            "passed": self.passed,
        }


@dataclass
class NetworkPolicy:
    policy_id: str = field(default_factory=lambda: f"net-{uuid.uuid4().hex[:8]}")
    vpc_only: bool = True
    public_exposure: bool = False
    mtls_required: bool = True
    tls_version: str = "1.3"
    allowed_endpoints: List[str] = field(default_factory=list)
    private_link: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "vpc_only": self.vpc_only,
            "public_exposure": self.public_exposure,
            "mtls_required": self.mtls_required,
            "tls_version": self.tls_version,
            "allowed_endpoints": self.allowed_endpoints,
            "private_link": self.private_link,
        }


@dataclass
class CryptoVaultResult:
    result_id: str = field(default_factory=lambda: f"crypto-{uuid.uuid4().hex[:8]}")
    key_id: str = ""
    encryption_at_rest: bool = True
    transit_tls_version: str = "1.3"
    secret_handle: str = ""
    lease_expires_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "key_id": self.key_id,
            "encryption_at_rest": self.encryption_at_rest,
            "transit_tls_version": self.transit_tls_version,
            "secret_handle": self.secret_handle,
            "lease_expires_at": self.lease_expires_at,
        }


@dataclass
class InferencePrivacyReport:
    report_id: str = field(default_factory=lambda: f"infpriv-{uuid.uuid4().hex[:8]}")
    request_id: str = ""
    extraction_attempt: bool = False
    pii_in_input: bool = False
    pii_in_output: bool = False
    secrets_in_output: bool = False
    blocked: bool = False
    requires_hitl: bool = False
    findings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "request_id": self.request_id,
            "extraction_attempt": self.extraction_attempt,
            "pii_in_input": self.pii_in_input,
            "pii_in_output": self.pii_in_output,
            "secrets_in_output": self.secrets_in_output,
            "blocked": self.blocked,
            "requires_hitl": self.requires_hitl,
            "findings": self.findings,
        }


@dataclass
class WORMAuditEntry:
    entry_id: str = field(default_factory=lambda: f"worm-{uuid.uuid4().hex[:8]}")
    event_type: str = ""
    actor: str = ""
    resource: str = ""
    action: str = ""
    timestamp: float = field(default_factory=time.time)
    pii_redacted: bool = True
    hash_chain: str = ""
    compliance_tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "event_type": self.event_type,
            "actor": self.actor,
            "resource": self.resource,
            "action": self.action,
            "timestamp": self.timestamp,
            "pii_redacted": self.pii_redacted,
            "hash_chain": self.hash_chain,
            "compliance_tags": self.compliance_tags,
        }


@dataclass
class ModelCard:
    card_id: str = field(default_factory=lambda: f"card-{uuid.uuid4().hex[:8]}")
    model_name: str = ""
    intended_use: str = ""
    training_data_summary: str = ""
    privacy_controls: List[str] = field(default_factory=list)
    dp_epsilon: float = 0.0
    mi_risk: str = "unknown"
    limitations: List[str] = field(default_factory=list)
    compliance_frameworks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "card_id": self.card_id,
            "model_name": self.model_name,
            "intended_use": self.intended_use,
            "training_data_summary": self.training_data_summary,
            "privacy_controls": self.privacy_controls,
            "dp_epsilon": self.dp_epsilon,
            "mi_risk": self.mi_risk,
            "limitations": self.limitations,
            "compliance_frameworks": self.compliance_frameworks,
        }


@dataclass
class DataSheet:
    sheet_id: str = field(default_factory=lambda: f"sheet-{uuid.uuid4().hex[:8]}")
    dataset_id: str = ""
    source: str = ""
    sensitive_attributes: List[str] = field(default_factory=list)
    anonymization_method: str = ""
    retention_hours: float = 0.0
    purpose: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sheet_id": self.sheet_id,
            "dataset_id": self.dataset_id,
            "source": self.source,
            "sensitive_attributes": self.sensitive_attributes,
            "anonymization_method": self.anonymization_method,
            "retention_hours": self.retention_hours,
            "purpose": self.purpose,
        }


@dataclass
class PrivacyPipelineState:
    pipeline_id: str = field(default_factory=lambda: f"pp-{uuid.uuid4().hex[:8]}")
    contract: Optional[DataContract] = None
    deid: Optional[DeIdentificationResult] = None
    retention: Optional[DataRetentionDecision] = None
    dp_config: Optional[DPTrainingConfig] = None
    dp_result: Optional[DPTrainingResult] = None
    mi_report: Optional[MembershipInferenceReport] = None
    network_policy: Optional[NetworkPolicy] = None
    crypto: Optional[CryptoVaultResult] = None
    model_card: Optional[ModelCard] = None
    data_sheet: Optional[DataSheet] = None
    status: str = "pending"
    audit_log: List[WORMAuditEntry] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "contract": self.contract.to_dict() if self.contract else None,
            "deid": self.deid.to_dict() if self.deid else None,
            "retention": self.retention.to_dict() if self.retention else None,
            "dp_config": self.dp_config.to_dict() if self.dp_config else None,
            "dp_result": self.dp_result.to_dict() if self.dp_result else None,
            "mi_report": self.mi_report.to_dict() if self.mi_report else None,
            "network_policy": self.network_policy.to_dict() if self.network_policy else None,
            "crypto": self.crypto.to_dict() if self.crypto else None,
            "model_card": self.model_card.to_dict() if self.model_card else None,
            "data_sheet": self.data_sheet.to_dict() if self.data_sheet else None,
            "status": self.status,
            "audit_log": [e.to_dict() for e in self.audit_log],
        }
