"""Modelos de datos para UC-276 — Recursive Prompting.

Estructuras inmutables que representan:
- Niveles de calidad (QualityLevel)
- Estrategias de refinamiento (RefinementStrategy)
- Criterios de calidad (QualityCriteria)
- Reportes de calidad (QualityReport)
- Versiones recursivas (RecursiveVersion)
- Sesiones completas (RecursiveSession)

Inspirado en:
- hankbesser/recursive-agents: historial transparente de versiones.
- Gödel Agent: auto-referencia con verificación.
- clawinfra/rsi-loop: Observe → Analyze → Fix → Verify.
"""
from __future__ import annotations

import hashlib
import time
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ============================================================
# Enumeraciones
# ============================================================

class QualityLevel(str, Enum):
    """Niveles de calidad del output."""
    UNACCEPTABLE = "unacceptable"   # < 0.3
    POOR = "poor"                   # 0.3 - 0.5
    ACCEPTABLE = "acceptable"       # 0.5 - 0.7
    GOOD = "good"                   # 0.7 - 0.85
    EXCELLENT = "excellent"         # 0.85 - 0.95
    OUTSTANDING = "outstanding"     # > 0.95


class RefinementStrategy(str, Enum):
    """Estrategias de refinamiento para el ciclo recursivo."""
    CLARIFY = "clarify"
    CONCISE = "concise"
    EXPAND = "expand"
    CORRECT = "correct"
    RESTRUCTURE = "restructure"
    VALIDATE = "validate"
    OPTIMIZE = "optimize"
    ADAPT_AUDIENCE = "adapt_audience"


class SessionStatus(str, Enum):
    """Estado de la sesión recursiva."""
    RUNNING = "running"
    CONVERGED = "converged"
    STAGNATED = "stagnated"
    MAX_ITERATIONS = "max_iterations"
    FAILED = "failed"


# ============================================================
# Criterios de Calidad
# ============================================================

class QualityCriteria(BaseModel):
    """Criterio de calidad para evaluar outputs."""
    name: str
    weight: float = Field(ge=0.0, le=1.0)
    min_threshold: float = Field(ge=0.0, le=1.0)
    target: float = Field(ge=0.0, le=1.0)
    description: str = ""


# ============================================================
# Reporte de Calidad
# ============================================================

class QualityReport(BaseModel):
    """Reporte de evaluación de calidad de una versión."""
    version_id: str
    overall_score: float = Field(ge=0.0, le=1.0)
    quality_level: QualityLevel
    criteria_scores: Dict[str, float]
    issues: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    meets_threshold: bool
    meets_target: bool

    @classmethod
    def from_scores(cls, version_id: str, criteria: List[QualityCriteria],
                    scores: Dict[str, float]) -> "QualityReport":
        """Construye reporte a partir de scores por criterio."""
        weighted_sum = 0.0
        total_weight = 0.0
        issues: List[str] = []
        strengths: List[str] = []
        all_meet_threshold = True
        all_meet_target = True

        for c in criteria:
            score = scores.get(c.name, 0.0)
            weighted_sum += score * c.weight
            total_weight += c.weight
            if score < c.min_threshold:
                issues.append(f"{c.name}: {score:.2f} < min {c.min_threshold:.2f}")
                all_meet_threshold = False
            elif score >= c.target:
                strengths.append(f"{c.name}: {score:.2f} >= target {c.target:.2f}")
            else:
                all_meet_target = False

        overall = weighted_sum / total_weight if total_weight > 0 else 0.0
        level = cls._classify_level(overall)

        return cls(
            version_id=version_id,
            overall_score=round(overall, 4),
            quality_level=level,
            criteria_scores={k: round(v, 4) for k, v in scores.items()},
            issues=issues,
            strengths=strengths,
            meets_threshold=all_meet_threshold,
            meets_target=all_meet_target,
        )

    @staticmethod
    def _classify_level(score: float) -> QualityLevel:
        if score >= 0.95:
            return QualityLevel.OUTSTANDING
        elif score >= 0.85:
            return QualityLevel.EXCELLENT
        elif score >= 0.7:
            return QualityLevel.GOOD
        elif score >= 0.5:
            return QualityLevel.ACCEPTABLE
        elif score >= 0.3:
            return QualityLevel.POOR
        return QualityLevel.UNACCEPTABLE


# ============================================================
# Versión Recursiva
# ============================================================

class RecursiveVersion(BaseModel):
    """Una versión en el ciclo recursivo de refinamiento."""
    version_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    iteration: int
    content: str
    content_hash: str = ""
    parent_version: Optional[str] = None
    refinement_strategy: Optional[RefinementStrategy] = None
    refinement_prompt: Optional[str] = None
    quality_report: Optional[QualityReport] = None
    delta_from_parent: Optional[float] = None
    timestamp: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.content_hash:
            object.__setattr__(self, "content_hash",
                               hashlib.sha256(self.content.encode()).hexdigest()[:16])

    @classmethod
    def create(cls, iteration: int, content: str,
               parent_version: Optional[str] = None,
               strategy: Optional[RefinementStrategy] = None,
               prompt: Optional[str] = None,
               metadata: Optional[Dict] = None) -> "RecursiveVersion":
        h = hashlib.sha256(content.encode()).hexdigest()[:16]
        return cls(
            iteration=iteration,
            content=content,
            content_hash=h,
            parent_version=parent_version,
            refinement_strategy=strategy,
            refinement_prompt=prompt,
            metadata=metadata or {},
        )


# ============================================================
# Sesión Recursiva
# ============================================================

class RecursiveSession(BaseModel):
    """Sesión completa del ciclo recursivo de prompting."""
    session_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    agent_id: str
    task_description: str
    initial_input: str
    versions: List[RecursiveVersion] = Field(default_factory=list)
    final_version_id: Optional[str] = None
    total_iterations: int = 0
    status: SessionStatus = SessionStatus.RUNNING
    convergence_reason: Optional[str] = None
    total_duration_seconds: float = 0.0
    session_hash: Optional[str] = None

    @property
    def final_version(self) -> Optional[RecursiveVersion]:
        if self.final_version_id:
            return next(
                (v for v in self.versions if v.version_id == self.final_version_id), None
            )
        return self.versions[-1] if self.versions else None

    @property
    def improvement_trajectory(self) -> List[float]:
        return [
            v.quality_report.overall_score
            for v in self.versions
            if v.quality_report
        ]

    @property
    def final_score(self) -> float:
        fv = self.final_version
        if fv and fv.quality_report:
            return fv.quality_report.overall_score
        return 0.0

    def compute_hash(self) -> str:
        import json
        payload = json.dumps({
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "task": self.task_description[:100],
            "iterations": self.total_iterations,
            "final_score": self.final_score,
            "version_hashes": [v.content_hash for v in self.versions],
        }, sort_keys=True).encode()
        return hashlib.sha256(payload).hexdigest()
