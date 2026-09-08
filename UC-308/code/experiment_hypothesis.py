"""UC-308 — ExperimentHypothesis: formalización de hipótesis de mejora.

Toda experimentación Champion–Challenger parte de una hipótesis versionada:
- Qué se quiere mejorar (métrica objetivo).
- Por qué se espera mejora (justificación).
- Qué cambio se introduce (challenger).
- Criterios de éxito y de rollback.
- Aprobador y trazabilidad.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class HypothesisStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


@dataclass
class ExperimentHypothesis:
    """Hipótesis versionada de mejora para un experimento."""
    hypothesis_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    experiment_id: str = ""
    version: int = 1
    metric: str = ""  # métrica objetivo a mejorar
    target_improvement: float = 0.05
    challenger_change: str = ""  # descripción del cambio
    rationale: str = ""  # justificación
    success_criteria: Dict[str, Any] = field(default_factory=dict)
    rollback_criteria: Dict[str, Any] = field(default_factory=dict)
    status: HypothesisStatus = HypothesisStatus.DRAFT
    approved_by: Optional[str] = None
    approved_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    superseded_by: Optional[str] = None
    trace_id: str = ""

    def compute_hash(self) -> str:
        payload = {
            "hypothesis_id": self.hypothesis_id,
            "experiment_id": self.experiment_id,
            "version": self.version,
            "metric": self.metric,
            "target_improvement": self.target_improvement,
            "challenger_change": self.challenger_change,
            "rationale": self.rationale,
            "success_criteria": self.success_criteria,
            "rollback_criteria": self.rollback_criteria,
            "status": self.status.value,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "created_at": self.created_at,
            "superseded_by": self.superseded_by,
            "trace_id": self.trace_id,
        }
        canonical = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def approve(self, approved_by: str, trace_id: str) -> None:
        if self.status != HypothesisStatus.DRAFT:
            raise ValueError(f"cannot approve hypothesis in state {self.status}")
        self.status = HypothesisStatus.APPROVED
        self.approved_by = approved_by
        self.approved_at = time.time()
        self.trace_id = trace_id

    def reject(self) -> None:
        self.status = HypothesisStatus.REJECTED

    def supersede(self, new_hypothesis_id: str) -> None:
        self.status = HypothesisStatus.SUPERSEDED
        self.superseded_by = new_hypothesis_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "experiment_id": self.experiment_id,
            "version": self.version,
            "metric": self.metric,
            "target_improvement": self.target_improvement,
            "challenger_change": self.challenger_change,
            "rationale": self.rationale,
            "success_criteria": self.success_criteria,
            "rollback_criteria": self.rollback_criteria,
            "status": self.status.value,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "created_at": self.created_at,
            "superseded_by": self.superseded_by,
            "trace_id": self.trace_id,
            "hypothesis_hash": self.compute_hash(),
        }


class HypothesisRegistry:
    """Registro versionado de hipótesis de experimentos."""

    def __init__(self):
        self._hypotheses: Dict[str, List[ExperimentHypothesis]] = {}

    def create(
        self,
        experiment_id: str,
        metric: str,
        target_improvement: float,
        challenger_change: str,
        rationale: str,
        success_criteria: Optional[Dict[str, Any]] = None,
        rollback_criteria: Optional[Dict[str, Any]] = None,
    ) -> ExperimentHypothesis:
        if experiment_id not in self._hypotheses:
            self._hypotheses[experiment_id] = []
        version = len(self._hypotheses[experiment_id]) + 1
        hyp = ExperimentHypothesis(
            experiment_id=experiment_id,
            version=version,
            metric=metric,
            target_improvement=target_improvement,
            challenger_change=challenger_change,
            rationale=rationale,
            success_criteria=success_criteria or {},
            rollback_criteria=rollback_criteria or {},
        )
        self._hypotheses[experiment_id].append(hyp)
        return hyp

    def get_active(self, experiment_id: str) -> Optional[ExperimentHypothesis]:
        chain = self._hypotheses.get(experiment_id, [])
        for hyp in reversed(chain):
            if hyp.status in (HypothesisStatus.DRAFT, HypothesisStatus.APPROVED):
                return hyp
        return None

    def approve(self, experiment_id: str, hypothesis_id: str, approved_by: str, trace_id: str) -> ExperimentHypothesis:
        chain = self._hypotheses.get(experiment_id, [])
        for hyp in chain:
            if hyp.hypothesis_id == hypothesis_id:
                hyp.approve(approved_by, trace_id)
                return hyp
        raise ValueError("hypothesis not found")

    def to_dict(self) -> Dict[str, Any]:
        return {
            exp: [h.to_dict() for h in chain]
            for exp, chain in self._hypotheses.items()
        }
