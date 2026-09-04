"""Modelos Pydantic para UC-307: evaluación de agentes autónomos y evolución de ADN."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class DecisionAction(str, Enum):
    """Acciones que el orquestador central puede ordenar sobre un agente."""

    PERSIST = "persist"
    ADJUST_PARAMS = "adjust_params"
    RETRAIN = "retrain"
    MUTATE = "mutate"
    ELIMINATE = "eliminate"
    GROW_CROSSOVER = "grow_crossover"
    GROW_RANDOM = "grow_random"


class EfficiencyMetrics(BaseModel):
    """Métricas de eficiencia del agente (Nivel 3)."""

    tokens_used: int = Field(ge=0, description="Tokens consumidos por la ejecución")
    tool_calls: int = Field(ge=0, description="Llamadas a herramientas externas")
    latency_seconds: float = Field(ge=0.0, description="Latencia de extremo a extremo en segundos")
    cost_usd: float = Field(0.0, ge=0.0, description="Costo estimado en USD (opcional)")


class AgentDNA(BaseModel):
    """Representación genética del agente: hiperparámetros que definen su comportamiento."""

    agent_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    version: int = Field(default=1, ge=1)
    hyperparams: Dict[str, float] = Field(
        default_factory=dict,
        description="Hiperparámetros del agente (ej. learning_rate, temperature, top_p)",
    )
    parent_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("hyperparams")
    @classmethod
    def ensure_numbers(cls, v: Dict[str, Any]) -> Dict[str, float]:
        return {str(k): float(v[k]) for k in v}

    def model_dump_json_safe(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "version": self.version,
            "hyperparams": self.hyperparams,
            "parent_ids": self.parent_ids,
            "created_at": self.created_at.isoformat(),
        }


class EvaluationInput(BaseModel):
    """Payload de entrada del orquestador central para evaluar un agente."""

    agent_id: str = Field(description="Identificador único del agente")
    task_success_rate: float = Field(ge=0.0, le=1.0, description="Tasa de éxito en tareas ejecutadas (0..1)")
    quality_score: float = Field(
        ge=0.0, le=5.0,
        description="Puntuación de calidad: escala 1..5 o normalizada 0..1.",
    )
    quality_scale: float = Field(
        default=5.0, ge=0.1,
        description="Escala máxima de quality_score. Por defecto 5.0 (escala 1..5). "
                    "Si quality_score ya está en 0..1, enviar quality_scale=1.0.",
    )
    efficiency: EfficiencyMetrics
    task_description: Optional[str] = Field(None, description="Descripción de la tarea para el LLM Juez")
    result_text: Optional[str] = Field(None, description="Resultado del agente para evaluación subjetiva")
    dna: Optional[AgentDNA] = Field(None, description="ADN actual del agente (opcional, para evolución)")
    mate_dna: Optional[AgentDNA] = Field(None, description="Segundo progenitor para cruza (opcional)")


class AgentEvaluation(BaseModel):
    """Resultado del análisis de performance de un agente."""

    evaluation_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    task_success_rate: float
    quality_score: float
    normalized_quality: float = Field(..., ge=0.0, le=1.0)
    efficiency: EfficiencyMetrics
    efficiency_score: float = Field(..., ge=0.0, le=1.0)
    fitness: float = Field(..., ge=0.0, le=1.0)
    verdict: DecisionAction
    actions: List[DecisionAction] = Field(default_factory=list)
    reasoning: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_dump_json_safe(self) -> Dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "agent_id": self.agent_id,
            "task_success_rate": self.task_success_rate,
            "quality_score": self.quality_score,
            "normalized_quality": self.normalized_quality,
            "efficiency": self.efficiency.model_dump(),
            "efficiency_score": self.efficiency_score,
            "fitness": self.fitness,
            "verdict": self.verdict.value,
            "actions": [a.value for a in self.actions],
            "reasoning": self.reasoning,
            "generated_at": self.generated_at.isoformat(),
        }


class EvolutionResult(BaseModel):
    """Resultado de aplicar una acción evolutiva a un agente."""

    original_agent_id: str
    action: DecisionAction
    child_dna: Optional[AgentDNA] = None
    adjusted_dna: Optional[AgentDNA] = None
    eliminated: bool = False
    reason: str

    def model_dump_json_safe(self) -> Dict[str, Any]:
        return {
            "original_agent_id": self.original_agent_id,
            "action": self.action.value,
            "child_dna": self.child_dna.model_dump_json_safe() if self.child_dna else None,
            "adjusted_dna": self.adjusted_dna.model_dump_json_safe() if self.adjusted_dna else None,
            "eliminated": self.eliminated,
            "reason": self.reason,
        }


class TaskSimulation(BaseModel):
    """Entrada para simular una tarea y evaluarla con el LLM Juez."""

    description: str = "Tarea de ejemplo"
    task_type: str = "unknown"
    subjective: bool = False
    expected: str = ""
