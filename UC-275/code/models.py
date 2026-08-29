"""Modelos para UC-275 — Autorreflexión de Agentes.

Cubre todas las estructuras del ciclo de autorreflexión:
- ActionTrace: traza atómica de una acción ejecutada.
- OutcomeObservation: observación del resultado.
- SelfEvaluation: evaluación interna multi-criterio.
- RootCauseAnalysis: análisis de causa raíz.
- RefinementProposal: propuesta de refinamiento.
- ReflectionEpisode: episodio completo de autorreflexión.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# Enums
# ============================================================

class ReflectionOutcome(str, Enum):
    """Resultado de una acción evaluada."""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    FAILURE = "failure"


class CauseCategory(str, Enum):
    """Categorías de causa raíz."""
    model_error = "model_error"
    data_stale = "data_stale"
    strategy_flaw = "strategy_flaw"
    execution_error = "execution_error"
    external_shock = "external_shock"
    parameter_miscalibration = "parameter_miscalibration"


# ============================================================
# Data Classes (sin Pydantic, para rendimiento)
# ============================================================

@dataclass
class ActionTrace:
    """Traza atómica de una acción ejecutada."""
    agent_id: str
    action_type: str
    action_params: Dict[str, Any]
    trace_id: str = field(default_factory=lambda: uuid4().hex[:16])
    timestamp: float = field(default_factory=time.time)
    context_snapshot: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OutcomeObservation:
    """Observación del resultado de una acción."""
    trace_id: str
    actual_outcome: Dict[str, Any]
    expected_outcome: Dict[str, Any]
    metrics: Dict[str, float]
    timestamp: float = field(default_factory=time.time)
    external_feedback: Optional[Dict[str, Any]] = None


# ============================================================
# Pydantic Models (para validación + serialización)
# ============================================================

class SelfEvaluation(BaseModel):
    """Evaluación interna del rendimiento — multi-criterio ponderado."""
    model_config = ConfigDict(frozen=True)

    trace_id: str
    outcome: ReflectionOutcome
    score: float = Field(ge=0.0, le=1.0)
    metric_breakdown: Dict[str, float]
    expectations_met: bool
    deviations: List[str] = Field(default_factory=list)
    severity: float = Field(ge=0.0, le=1.0)

    @property
    def needs_reflection(self) -> bool:
        return self.score < 0.7 or self.severity > 0.5


class RootCauseAnalysis(BaseModel):
    """Análisis de causa raíz con heurísticas + razonamiento estructurado."""
    model_config = ConfigDict(frozen=True)

    trace_id: str
    primary_cause: str
    contributing_factors: List[str] = Field(default_factory=list)
    category: CauseCategory
    confidence: float = Field(ge=0.0, le=1.0)


class RefinementProposal(BaseModel):
    """Propuesta de refinamiento con análisis coste-beneficio."""
    model_config = ConfigDict(frozen=True)

    trace_id: str
    iteration: int
    proposed_changes: Dict[str, Any]
    rationale: str
    expected_improvement: float
    risk_of_change: float = Field(ge=0.0, le=1.0)

    @property
    def net_benefit(self) -> float:
        return self.expected_improvement - self.risk_of_change


class ReflectionEpisode(BaseModel):
    """Episodio completo de autorreflexión (ACT→OBSERVE→EVALUATE→REFLECT→REFINE→FINALIZE)."""
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    episode_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    agent_id: str
    trace_id: str
    action: ActionTrace
    observation: OutcomeObservation
    evaluation: SelfEvaluation
    root_cause: Optional[RootCauseAnalysis] = None
    refinements: List[RefinementProposal] = Field(default_factory=list)
    iterations: int = 0
    final_outcome: Optional[ReflectionOutcome] = None
    final_score: Optional[float] = None
    duration_seconds: float = 0.0
    reflection_hash: Optional[str] = None

    def compute_hash(self) -> str:
        """Hash SHA-256 del episodio para auditoría on-chain."""
        content = json.dumps({
            "episode_id": self.episode_id,
            "agent_id": self.agent_id,
            "trace_id": self.trace_id,
            "iterations": self.iterations,
            "final_outcome": self.final_outcome.value if self.final_outcome else None,
            "final_score": self.final_score,
        }, sort_keys=True)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ============================================================
# API Response Models
# ============================================================

class AgentStatus(BaseModel):
    """Estado de un agente reflexivo."""
    agent_id: str
    total_episodes: int = 0
    avg_score: float = 0.0
    success_rate: float = 0.0
    total_iterations: int = 0
    improvement_rate: float = 0.0


class SystemStatus(BaseModel):
    """Estado del sistema de autorreflexión."""
    total_agents: int = 0
    total_episodes: int = 0
    avg_score: float = 0.0
    avg_iterations: float = 0.0
    convergence_rate: float = 0.0
    memory_size: int = 0
