"""
UC-703 fine_tuning — Modelos de dominio para el ciclo de vida de fine-tuning.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DatasetVersion:
    dataset_id: str = field(default_factory=lambda: f"ds-{uuid.uuid4().hex[:8]}")
    version: str = "v1"
    prompt_template: str = ""
    seed: int = 42
    splits: Dict[str, str] = field(default_factory=dict)  # name -> uri
    num_samples: int = 0
    audit_hash: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "version": self.version,
            "prompt_template": self.prompt_template,
            "seed": self.seed,
            "splits": self.splits,
            "num_samples": self.num_samples,
            "audit_hash": self.audit_hash,
            "created_at": self.created_at,
        }


@dataclass
class CurationResult:
    result_id: str = field(default_factory=lambda: f"cur-{uuid.uuid4().hex[:8]}")
    dataset_id: str = ""
    cleaned_samples: int = 0
    duplicates_removed: int = 0
    hitl_flagged_samples: List[Dict[str, Any]] = field(default_factory=list)
    template_valid: bool = False
    output_uri: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "dataset_id": self.dataset_id,
            "cleaned_samples": self.cleaned_samples,
            "duplicates_removed": self.duplicates_removed,
            "hitl_flagged_samples": self.hitl_flagged_samples,
            "template_valid": self.template_valid,
            "output_uri": self.output_uri,
        }


@dataclass
class LeakageReport:
    report_id: str = field(default_factory=lambda: f"leak-{uuid.uuid4().hex[:8]}")
    dataset_id: str = ""
    ngram_overlap_score: float = 0.0
    embedding_overlap_score: float = 0.0
    leaked_samples: List[Dict[str, Any]] = field(default_factory=list)
    passed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "dataset_id": self.dataset_id,
            "ngram_overlap_score": self.ngram_overlap_score,
            "embedding_overlap_score": self.embedding_overlap_score,
            "leaked_samples": self.leaked_samples,
            "passed": self.passed,
        }


@dataclass
class ResourcePlan:
    plan_id: str = field(default_factory=lambda: f"rp-{uuid.uuid4().hex[:8]}")
    strategy: str = "lora"  # full, lora, qlora
    instance_type: str = ""
    use_spot: bool = False
    estimated_cost_usd: float = 0.0
    estimated_duration_hours: float = 0.0
    num_gpus: int = 1
    zero_stage: int = 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "strategy": self.strategy,
            "instance_type": self.instance_type,
            "use_spot": self.use_spot,
            "estimated_cost_usd": self.estimated_cost_usd,
            "estimated_duration_hours": self.estimated_duration_hours,
            "num_gpus": self.num_gpus,
            "zero_stage": self.zero_stage,
        }


@dataclass
class TrainingRunConfig:
    run_id: str = field(default_factory=lambda: f"run-{uuid.uuid4().hex[:8]}")
    dataset_id: str = ""
    base_model: str = ""
    resource_plan: Optional[ResourcePlan] = None
    hyperparams: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, running, paused, completed, failed
    checkpoint_uris: List[str] = field(default_factory=list)
    metrics: Dict[str, List[float]] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "dataset_id": self.dataset_id,
            "base_model": self.base_model,
            "resource_plan": self.resource_plan.to_dict() if self.resource_plan else None,
            "hyperparams": self.hyperparams,
            "status": self.status,
            "checkpoint_uris": self.checkpoint_uris,
            "metrics": self.metrics,
            "created_at": self.created_at,
        }


@dataclass
class EvaluationReport:
    report_id: str = field(default_factory=lambda: f"eval-{uuid.uuid4().hex[:8]}")
    run_id: str = ""
    domain_score: float = 0.0
    general_score: float = 0.0
    catastrophic_forgetting_score: float = 0.0  # negative = degradation
    judge_scores: Dict[str, float] = field(default_factory=dict)
    passed: bool = False
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "run_id": self.run_id,
            "domain_score": self.domain_score,
            "general_score": self.general_score,
            "catastrophic_forgetting_score": self.catastrophic_forgetting_score,
            "judge_scores": self.judge_scores,
            "passed": self.passed,
            "recommendations": self.recommendations,
        }


@dataclass
class ModelBundle:
    bundle_id: str = field(default_factory=lambda: f"bundle-{uuid.uuid4().hex[:8]}")
    base_model: str = ""
    adapter_uri: str = ""
    prompt_template: str = ""
    generation_params: Dict[str, Any] = field(default_factory=dict)
    dataset_version_id: str = ""
    training_run_id: str = ""
    audit_hash: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "base_model": self.base_model,
            "adapter_uri": self.adapter_uri,
            "prompt_template": self.prompt_template,
            "generation_params": self.generation_params,
            "dataset_version_id": self.dataset_version_id,
            "training_run_id": self.training_run_id,
            "audit_hash": self.audit_hash,
            "created_at": self.created_at,
        }


@dataclass
class Deployment:
    deployment_id: str = field(default_factory=lambda: f"dep-{uuid.uuid4().hex[:8]}")
    bundle_id: str = ""
    serving_mode: str = "lora_fused"  # lora_fused, multi_lora
    traffic_percent: float = 0.0
    status: str = "pending"  # pending, canary, stable, rolled_back
    metrics: Dict[str, Any] = field(default_factory=dict)
    sLo: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deployment_id": self.deployment_id,
            "bundle_id": self.bundle_id,
            "serving_mode": self.serving_mode,
            "traffic_percent": self.traffic_percent,
            "status": self.status,
            "metrics": self.metrics,
            "sLo": self.sLo,
            "created_at": self.created_at,
        }


@dataclass
class DriftReport:
    report_id: str = f"drift-{uuid.uuid4().hex[:8]}"
    deployment_id: str = ""
    data_drift_score: float = 0.0
    concept_drift_score: float = 0.0
    hallucination_rate: float = 0.0
    threshold_violated: bool = False
    samples: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "deployment_id": self.deployment_id,
            "data_drift_score": self.data_drift_score,
            "concept_drift_score": self.concept_drift_score,
            "hallucination_rate": self.hallucination_rate,
            "threshold_violated": self.threshold_violated,
            "samples": self.samples,
        }


@dataclass
class FeedbackItem:
    feedback_id: str = field(default_factory=lambda: f"fb-{uuid.uuid4().hex[:8]}")
    deployment_id: str = ""
    input_text: str = ""
    output_text: str = ""
    label: str = ""  # good, bad, corrected
    corrected_output: str = ""
    source: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "deployment_id": self.deployment_id,
            "input_text": self.input_text,
            "output_text": self.output_text,
            "label": self.label,
            "corrected_output": self.corrected_output,
            "source": self.source,
            "timestamp": self.timestamp,
        }


@dataclass
class ClosedLoopCycle:
    cycle_id: str = field(default_factory=lambda: f"loop-{uuid.uuid4().hex[:8]}")
    deployment_id: str = ""
    triggered_by: str = ""  # drift, feedback_count, schedule
    new_dataset_id: str = ""
    status: str = "pending"  # pending, approved, training, completed, rejected
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "deployment_id": self.deployment_id,
            "triggered_by": self.triggered_by,
            "new_dataset_id": self.new_dataset_id,
            "status": self.status,
            "priority": self.priority,
        }
