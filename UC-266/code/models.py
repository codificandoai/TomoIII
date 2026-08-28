"""Modelos de datos para UC-266 - Agente Resiliente y Robusto."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TravelPlanRequest(BaseModel):
    """Solicitud de planificación de viaje."""

    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None
    travelers: int = Field(default=1, ge=1)
    budget: Optional[float] = None
    currency: str = Field(default="USD")
    preferences: Dict[str, Any] = Field(default_factory=dict)
    constraints: List[str] = Field(default_factory=list)
    confirm_irreversible: bool = Field(default=False)
    predict_delays: bool = Field(default=True)
    user_id: str = Field(default="anonymous")
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    def to_state(self) -> Dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TravelPlanRequest":
        return cls(**data)


class PlanAction(BaseModel):
    """Acción dentro de un plan (elegir vuelo, hotel, actividad)."""

    action_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    step: int = 0
    action_type: str = Field(default="flight")  # flight, hotel, activity
    item_id: str = Field(default="")
    item_name: str = Field(default="")
    details: Dict[str, Any] = Field(default_factory=dict)
    estimated_cost: float = Field(default=0.0)
    estimated_success_prob: float = Field(default=1.0, ge=0.0, le=1.0)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class WorldModelState(BaseModel):
    """Representación del estado actual en el world model."""

    request_id: str = ""
    step: int = 0
    itinerary: List[Dict[str, Any]] = Field(default_factory=list)
    remaining_budget: Optional[float] = None
    total_cost: float = 0.0
    currency: str = "USD"
    preferences: Dict[str, Any] = Field(default_factory=dict)
    constraints: List[str] = Field(default_factory=list)
    completed: bool = False
    belief_state: Optional[Dict[str, Any]] = None

    def copy(self) -> "WorldModelState":
        return WorldModelState(**self.model_dump())

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class Transition(BaseModel):
    """Transición (s, a, s', r, p) aprendida o simulada."""

    transition_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    prev_state: Dict[str, Any] = Field(default_factory=dict)
    action: Dict[str, Any] = Field(default_factory=dict)
    next_state: Dict[str, Any] = Field(default_factory=dict)
    reward: float = 0.0
    probability: float = Field(default=1.0, ge=0.0, le=1.0)
    info: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class CandidatePlan(BaseModel):
    """Plan candidato generado por el motor de opciones."""

    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    strategy: str = Field(default="balanced")
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    estimated_total_cost: float = 0.0
    estimated_success_prob: float = 1.0
    simulations: List[Dict[str, Any]] = Field(default_factory=list)
    expected_utility: float = 0.0
    risk_score: float = 0.0
    alignment_score: float = 0.0
    final_score: float = 0.0
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class SimulationResult(BaseModel):
    """Resultado de una simulación Monte Carlo de un plan."""

    simulation_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    plan_id: str = ""
    outcome: Dict[str, Any] = Field(default_factory=dict)
    total_cost: float = 0.0
    utility: float = 0.0
    success: bool = True
    violated_constraints: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class PlanEvaluation(BaseModel):
    """Evaluación final de un plan por el crítico."""

    evaluation_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    plan_id: str = ""
    expected_utility: float = 0.0
    expected_cost: float = 0.0
    success_probability: float = 0.0
    risk_score: float = 0.0
    alignment_score: float = 0.0
    final_score: float = 0.0
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class WorldModelObservation(BaseModel):
    """Observación real usada para actualizar el world model."""

    observation_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    action_type: str = ""
    item_id: str = ""
    predicted_success_prob: float = 1.0
    actual_success: bool = True
    actual_cost: float = 0.0
    reward: float = 0.0
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ExecutionResult(BaseModel):
    """Resultado de ejecutar un plan en el mundo real."""

    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    plan_id: str = ""
    actions_results: List[Dict[str, Any]] = Field(default_factory=list)
    total_cost: float = 0.0
    successful: bool = True
    failed_actions: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class HiddenState(BaseModel):
    """Estado oculto del entorno en entornos parcialmente observables."""

    true_availability: Dict[str, int] = Field(default_factory=dict)
    true_delays: Dict[str, float] = Field(default_factory=dict)
    weather_condition: str = Field(default="unknown")
    market_pressure: float = Field(default=0.0)  # factor oculto que afecta precios

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class BeliefState(BaseModel):
    """Distribución de creencias sobre el estado oculto (particle filter)."""

    belief_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    particles: List[Dict[str, Any]] = Field(default_factory=list)
    weights: List[float] = Field(default_factory=list)
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class Observation(BaseModel):
    """Observación parcial y ruidosa del entorno."""

    observation_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    item_id: str = ""
    observed_price: float = 0.0
    observed_availability: int = 0
    observed_delay: float = 0.0
    weather: str = "unknown"
    noise_level: float = 0.0
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class TrainingBatch(BaseModel):
    """Lote de datos para reentrenar el world model."""

    batch_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    transitions: List[Dict[str, Any]] = Field(default_factory=list)
    observations: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ChangeEvent(BaseModel):
    """Evento de cambio del entorno detectado durante ejecución o planificación."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    event_type: str = ""  # weather, availability, delay, price, market, cancellation
    item_id: str = ""
    severity: float = Field(default=0.0, ge=0.0, le=1.0)
    detected_at_step: int = 0
    expected_impact: str = ""
    observed_data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class RecoveryPlan(BaseModel):
    """Plan de recuperación generado tras detectar un cambio."""

    recovery_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    trigger_event: Dict[str, Any] = Field(default_factory=dict)
    strategy: str = ""  # replan, backup, compensate, abort
    fallback_plan: Optional[Dict[str, Any]] = None
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    expected_success_prob: float = 1.0
    recovery_attempt: int = 1
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ResilienceLog(BaseModel):
    """Entrada de log del motor de resiliencia."""

    log_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    stage: str = ""  # detect, diagnose, recover, reflect
    message: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
