"""Modelos A2A y de comunicación entre agentes para UC-268.

Incluye:
- Agent Card con capacidades y esquemas de seguridad (A2A).
- Task, Message, Artifact, Part (A2A).
- Envelope interno con trazabilidad y control de TTL.
- Payloads del dominio de vuelos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# ============================================================
# A2A Agent Card
# ============================================================

class SecuritySchemeType(str, Enum):
    bearer = "bearer"
    api_key = "apiKey"
    oauth2 = "oauth2"
    openid_connect = "openIdConnect"


class AgentProvider(BaseModel):
    organization: str
    url: Optional[str] = None


class AgentCapability(BaseModel):
    skill_id: str
    name: str
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list)
    # Scopes requeridos para invocar esta skill
    scopes: List[str] = Field(default_factory=list)


class AgentSecurityScheme(BaseModel):
    scheme: SecuritySchemeType
    description: str = ""
    # OAuth2 / OIDC
    authorization_endpoint: Optional[str] = None
    token_endpoint: Optional[str] = None
    scopes: Dict[str, str] = Field(default_factory=dict)
    # API key
    in_header: Optional[str] = None


class AgentCard(BaseModel):
    """Tarjeta de presentación A2A de un agente."""

    name: str
    description: str
    url: str
    version: str
    provider: Optional[AgentProvider] = None
    documentation_url: Optional[str] = None
    capabilities: List[AgentCapability] = Field(default_factory=list)
    default_input_modes: List[str] = Field(default_factory=lambda: ["text", "json"])
    default_output_modes: List[str] = Field(default_factory=lambda: ["text", "json"])
    security_schemes: List[AgentSecurityScheme] = Field(default_factory=list)

    def supported_scopes(self) -> List[str]:
        scopes: set[str] = set()
        for scheme in self.security_schemes:
            scopes.update(scheme.scopes.keys())
        return sorted(scopes)


# ============================================================
# A2A Task / Message / Artifact
# ============================================================

class TaskStatus(str, Enum):
    submitted = "submitted"
    working = "working"
    input_required = "input-required"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class Part(BaseModel):
    type: Literal["text", "json", "file", "data"] = "text"
    content: Any = ""
    mime_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    role: Literal["user", "agent"] = "user"
    parts: List[Part] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Artifact(BaseModel):
    artifact_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    parts: List[Part] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    status: TaskStatus = TaskStatus.submitted
    session_id: Optional[str] = None
    messages: List[Message] = Field(default_factory=list)
    artifacts: List[Artifact] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    status_history: List[Dict[str, Any]] = Field(default_factory=list)
    final_output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def update_status(self, status: TaskStatus, detail: str = "") -> None:
        self.status = status
        self.status_history.append({
            "status": status.value,
            "detail": detail,
            "timestamp": datetime.utcnow().isoformat(),
        })


class JSONRPCRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)
    id: Optional[Union[str, int]] = None


class JSONRPCResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None


# ============================================================
# Dominio de vuelos (Pydantic en el borde)
# ============================================================

class AgentRole(str, Enum):
    PLANNER = "planner"
    SIMULATOR = "simulator"
    CRITIC = "critic"
    EXECUTOR = "executor"
    MONITOR = "monitor"
    USER_PROXY = "user_proxy"


class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class FlightClass(str, Enum):
    ECONOMY = "economy"
    PREMIUM = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"


class FlightSearchRequest(BaseModel):
    """Payload: solicitud de búsqueda de vuelos"""
    model_config = ConfigDict(strict=True, frozen=True)

    origin: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    destination: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    departure_date: datetime
    return_date: Optional[datetime] = None
    passengers: int = Field(ge=1, le=9, default=1)
    cabin_class: FlightClass = FlightClass.ECONOMY
    max_price_usd: Decimal = Field(gt=0, decimal_places=2)
    flexible_dates: bool = False

    @model_validator(mode="after")
    def validate_dates(self) -> "FlightSearchRequest":
        if self.return_date and self.return_date <= self.departure_date:
            raise ValueError("return_date must be after departure_date")
        if self.origin == self.destination:
            raise ValueError("origin and destination must differ")
        return self


class FlightOption(BaseModel):
    """Opción de vuelo individual"""
    model_config = ConfigDict(frozen=True)

    flight_number: str
    airline: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int
    price_usd: Decimal
    cabin_class: FlightClass
    seats_available: int
    co2_kg: float
    reliability_score: float = Field(ge=0.0, le=1.0)


class FlightSearchResponse(BaseModel):
    """Payload: respuesta de búsqueda"""
    options: List[FlightOption] = Field(default_factory=list)
    total_found: int
    search_duration_ms: int
    warnings: List[str] = Field(default_factory=list)


class SimulationRequest(BaseModel):
    """Payload: solicitud de simulación de plan"""
    plan_id: UUID
    flight_options: List[FlightOption]
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    simulation_horizon_hours: int = 72
    num_scenarios: int = Field(ge=10, le=10000, default=100)


class SimulationOutcome(BaseModel):
    """Resultado de un escenario simulado"""
    scenario_id: int
    total_cost_usd: Decimal
    total_travel_time_min: int
    connection_missed: bool
    disruption_probability: float = Field(ge=0.0, le=1.0)
    user_satisfaction_score: float = Field(ge=0.0, le=10.0)


class SimulationResponse(BaseModel):
    """Payload: respuesta de simulación"""
    plan_id: UUID
    scenarios: List[SimulationOutcome]
    expected_cost_usd: Decimal
    p95_cost_usd: Decimal
    risk_score: float = Field(ge=0.0, le=1.0)
    recommendation: Literal["approve", "revise", "reject"]


class CritiqueResponse(BaseModel):
    """Payload: evaluación crítica del plan"""
    plan_id: UUID
    verdict: Literal["approved", "needs_revision", "rejected"]
    strengths: List[str]
    weaknesses: List[str]
    suggested_alternatives: List[UUID]
    confidence: float = Field(ge=0.0, le=1.0)


class ExecutionReport(BaseModel):
    """Payload: reporte de ejecución"""
    plan_id: UUID
    status: Literal["success", "partial", "failed", "rolled_back"]
    bookings_confirmed: List[str]
    bookings_failed: List[str]
    total_charged_usd: Decimal
    confirmation_codes: List[str]
    error_details: Optional[str] = None


Payload = Union[
    FlightSearchRequest,
    FlightSearchResponse,
    SimulationRequest,
    SimulationResponse,
    CritiqueResponse,
    ExecutionReport,
    Task,
    Message,
    Artifact,
    Dict[str, Any],
]


# ============================================================
# Envelope interno de comunicación
# ============================================================

class MessageEnvelope(BaseModel):
    """Envolvente estándar de todo mensaje entre agentes."""

    model_config = ConfigDict(frozen=True)

    message_id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID = Field(default_factory=uuid4)
    causation_id: Optional[UUID] = None

    source_agent: AgentRole
    target_agent: AgentRole
    message_type: Literal[
        "flight.search_request",
        "flight.search_response",
        "plan.simulate_request",
        "plan.simulate_response",
        "plan.critique_response",
        "plan.execution_report",
        "system.error",
        "system.heartbeat",
        "a2a.task_request",
    ]

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    priority: Priority = Priority.NORMAL
    ttl_ms: int = Field(default=30_000, ge=100, le=600_000)
    schema_version: str = "1.0.0"
    trace_id: Optional[str] = None

    payload: Payload
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("payload", mode="before")
    @classmethod
    def validate_payload_matches_type(cls, v: Any, info) -> Any:
        type_to_model = {
            "flight.search_request": FlightSearchRequest,
            "flight.search_response": FlightSearchResponse,
            "plan.simulate_request": SimulationRequest,
            "plan.simulate_response": SimulationResponse,
            "plan.critique_response": CritiqueResponse,
            "plan.execution_report": ExecutionReport,
        }
        msg_type = info.data.get("message_type")
        expected = type_to_model.get(msg_type)
        if expected is not None:
            if isinstance(v, dict):
                return expected.model_validate(v)
            if not isinstance(v, expected):
                raise ValueError(
                    f"payload type mismatch: expected {expected.__name__} for {msg_type}"
                )
        return v

    def is_expired(self) -> bool:
        age_ms = (datetime.utcnow() - self.timestamp).total_seconds() * 1000
        return age_ms > self.ttl_ms

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, data: str) -> "MessageEnvelope":
        return cls.model_validate_json(data)


# ============================================================
# Dataclasses internas de alto rendimiento
# ============================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class InternalFlightOption:
    """Versión interna optimizada de FlightOption (sin validación)"""

    flight_number: str
    airline: str
    origin: str
    destination: str
    departure_ts: int
    arrival_ts: int
    duration_min: int
    price_cents: int
    cabin_class: str
    seats_available: int
    co2_kg: float
    reliability_score: float

    @classmethod
    def from_pydantic(cls, opt: FlightOption) -> "InternalFlightOption":
        return cls(
            flight_number=opt.flight_number,
            airline=opt.airline,
            origin=opt.origin,
            destination=opt.destination,
            departure_ts=int(opt.departure_time.timestamp()),
            arrival_ts=int(opt.arrival_time.timestamp()),
            duration_min=opt.duration_minutes,
            price_cents=int(opt.price_usd * 100),
            cabin_class=opt.cabin_class.value,
            seats_available=opt.seats_available,
            co2_kg=opt.co2_kg,
            reliability_score=opt.reliability_score,
        )

    def to_pydantic(self) -> FlightOption:
        return FlightOption(
            flight_number=self.flight_number,
            airline=self.airline,
            origin=self.origin,
            destination=self.destination,
            departure_time=datetime.fromtimestamp(self.departure_ts),
            arrival_time=datetime.fromtimestamp(self.arrival_ts),
            duration_minutes=self.duration_min,
            price_usd=Decimal(self.price_cents) / 100,
            cabin_class=FlightClass(self.cabin_class),
            seats_available=self.seats_available,
            co2_kg=self.co2_kg,
            reliability_score=self.reliability_score,
        )


@dataclass(slots=True, frozen=True, kw_only=True)
class InternalPlan:
    """Plan interno para procesamiento rápido"""

    plan_id: str
    options: tuple
    total_cost_cents: int
    estimated_risk: float
    created_at: int


@dataclass(slots=True)
class AgentMetrics:
    """Métricas acumulables (mutable para eficiencia)"""

    messages_sent: int = 0
    messages_received: int = 0
    errors: int = 0
    avg_latency_ms: float = 0.0
