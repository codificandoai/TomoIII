"""Modelos de datos para UC-292 - Sistema Multi-Agente de Trading."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ToolDefinition(BaseModel):
    """Definición de herramienta MCP con esquema de entrada."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    risk: str = "safe"  # safe | dangerous


class MarketTick(BaseModel):
    """Tick de mercado tick-by-tick."""

    timestamp: str
    symbol: str
    bid: float
    ask: float
    bid_size: float = 0.0
    ask_size: float = 0.0
    last_price: float
    volume: float = 0.0
    vwap: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class NewsItem(BaseModel):
    """Noticia o titular de mercado."""

    text: str
    source: str = "unknown"
    published_at: Optional[str] = None
    received_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ProcessedNews(BaseModel):
    """Noticia preprocesada con entidades y sentimiento."""

    text: str
    tokens: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    source_credibility: float = 0.5
    latency_seconds: float = 0.0
    sentiment: float = 0.0
    market_impact_historical: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class TechnicalSnapshot(BaseModel):
    """Indicadores técnicos de un instante."""

    symbol: str
    timestamp: str
    sma_fast: float = 0.0
    sma_slow: float = 0.0
    rsi: float = 50.0
    macd: float = 0.0
    macd_signal: float = 0.0
    atr: float = 0.0
    bollinger_position: float = 0.0
    obv: float = 0.0
    volume_trend: int = 0
    trend_direction: int = 0
    volatility: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class MarketSnapshot(BaseModel):
    """Estado estructurado del mercado percibido por el agente."""

    symbol: str
    timestamp: str
    latest_price: float
    features: TechnicalSnapshot
    news_sentiment: float = 0.0
    news_credibility: float = 0.5
    regime: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class Portfolio(BaseModel):
    """Portafolio del agente."""

    cash: float = 100_000.0
    positions: Dict[str, float] = Field(default_factory=dict)
    average_cost: Dict[str, float] = Field(default_factory=dict)
    margin_used: float = 0.0

    def market_value(self, prices: Dict[str, float]) -> float:
        value = self.cash
        for symbol, qty in self.positions.items():
            value += qty * prices.get(symbol, 0.0)
        return value

    def copy(self) -> "Portfolio":
        return Portfolio(**self.model_dump())

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class RiskConstraints(BaseModel):
    """Restricciones de riesgo operativo."""

    max_position_pct: float = 0.2
    max_drawdown_pct: float = 0.05
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    max_trade_notional: float = 100_000.0
    min_signal_confidence: float = 0.5
    max_orders_per_min: int = 10
    circuit_breaker_failures: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class TradingSignal(BaseModel):
    """Señal de trading generada por un agente analista."""

    symbol: str
    side: str = "HOLD"  # BUY, SELL, HOLD
    confidence: float = 0.0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    position_fraction: float = 0.0
    time_horizon: str = "short"
    reasoning: str = ""
    agent: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class TradingRequest(BaseModel):
    """Solicitud de análisis/ejecución del agente de trading."""

    symbols: List[str] = Field(default_factory=list)
    ticks: List[MarketTick] = Field(default_factory=list)
    news: List[NewsItem] = Field(default_factory=list)
    portfolio: Optional[Portfolio] = None
    constraints: Optional[RiskConstraints] = None
    risk_tolerance: str = "moderate"  # conservative | moderate | aggressive
    mode: str = "paper"  # paper | live | sim
    approved: bool = False
    user_id: str = "anonymous"
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradingRequest":
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class AgentAction(BaseModel):
    """Acción de trading ejecutable."""

    action_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    step: int = 0
    action_type: str = "ORDER"  # ORDER, HOLD, REBALANCE
    symbol: str = ""
    side: str = "HOLD"  # BUY, SELL, HOLD
    quantity: float = 0.0
    price: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class WorldModelState(BaseModel):
    """Estado interno del world model para simulación."""

    request_id: str = ""
    symbol: str = ""
    step: int = 0
    price: float = 0.0
    cash: float = 0.0
    position: float = 0.0
    features: Dict[str, Any] = Field(default_factory=dict)
    portfolio_value: float = 0.0
    done: bool = False

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


class CandidateStrategy(BaseModel):
    """Estrategia candidata de trading."""

    strategy_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    actions: List[AgentAction] = Field(default_factory=list)
    expected_return: float = 0.0
    expected_risk: float = 0.0
    sharpe: float = 0.0
    success_prob: float = 0.0
    risk_score: float = 0.0
    alignment_score: float = 0.0
    final_score: float = 0.0
    simulations: List[Dict[str, Any]] = Field(default_factory=list)
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class SimulationResult(BaseModel):
    """Resultado de una simulación Monte Carlo de una estrategia."""

    simulation_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    strategy_id: str = ""
    outcome: Dict[str, Any] = Field(default_factory=dict)
    total_return: float = 0.0
    utility: float = 0.0
    success: bool = True
    violated_constraints: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class StrategyEvaluation(BaseModel):
    """Evaluación final de una estrategia por el crítico."""

    evaluation_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    strategy_id: str = ""
    expected_return: float = 0.0
    expected_risk: float = 0.0
    success_probability: float = 0.0
    risk_score: float = 0.0
    alignment_score: float = 0.0
    final_score: float = 0.0
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ExecutionResult(BaseModel):
    """Resultado de ejecutar una orden en el exchange simulado."""

    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    strategy_id: str = ""
    status: str = "PENDING"  # FILLED, REJECTED, PARTIAL
    action: Dict[str, Any] = Field(default_factory=dict)
    filled_quantity: float = 0.0
    fill_price: float = 0.0
    fees: float = 0.0
    slippage: float = 0.0
    realized_pnl: float = 0.0
    remaining_cash: float = 0.0
    remaining_position: float = 0.0
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class WorldModelObservation(BaseModel):
    """Observación real usada para actualizar el world model."""

    observation_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    action_type: str = ""
    item_id: str = ""
    symbol: str = ""
    predicted_success_prob: float = 1.0
    actual_success: bool = True
    actual_cost: float = 0.0
    reward: float = 0.0
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class BeliefState(BaseModel):
    """Distribución de creencias sobre estado oculto."""

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
    observed_volatility: float = 0.0
    observed_volume: float = 0.0
    noise_level: float = 0.0
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class JuiceValidationResult(BaseModel):
    """Resultado de validación por Juice Agents."""

    validation_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    consensus_score: float = 0.0
    approved: bool = False
    issues: List[str] = Field(default_factory=list)
    agent_scores: Dict[str, float] = Field(default_factory=dict)
    confidence: float = 0.0
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class RiskAssessment(BaseModel):
    """Dictamen de riesgo sobre una señal o estrategia."""

    assessment_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    allowed: bool = False
    side: str = "HOLD"
    max_quantity: float = 0.0
    max_notional: float = 0.0
    risk_score: float = 0.0
    flags: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


# =============================================================================
# Modelos BDI + ReAct + Filtro Adversarial Juice (UC-293)
# =============================================================================
class CoTStep(BaseModel):
    """Un paso de razonamiento ReAct: pensamiento, acción y observación."""

    step: int = 0
    thought: str = ""
    action: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)
    observation: str = ""
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class BDIBeliefs(BaseModel):
    """Creencias estrictas del agente: solo hechos ground-truth del mercado."""

    symbol: str = ""
    current_price: float = 0.0
    cost_basis: float = 0.0
    latest_features: Dict[str, Any] = Field(default_factory=dict)
    regime: str = "unknown"
    news_sentiment: float = 0.0
    news_credibility: float = 0.5
    volatility: float = 0.0
    atr: float = 0.0
    rsi: float = 50.0
    trend_direction: int = 0
    empirical_success_prob: float = 0.5
    world_model_uncertainty: float = 1.0
    predicted_next_price: float = 0.0
    portfolio_cash: float = 0.0
    portfolio_position: float = 0.0
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class BDIDesires(BaseModel):
    """Deseos/Objetivos de negocio y restricciones duras."""

    primary_goal: str = "Maximizar el retorno ajustado por riesgo."
    secondary_goal: str = "Preservar capital y limitar drawdown."
    hard_constraints: List[str] = Field(default_factory=lambda: [
        "NUNCA operar sin señal de confianza suficiente.",
        "NUNCA exceder el tamaño máximo de posición.",
        "NUNCA ignorar una tendencia técnica contradictoria.",
    ])
    risk_tolerance: str = "moderate"
    min_signal_confidence: float = 0.5
    max_position_pct: float = 0.2
    max_drawdown_pct: float = 0.05
    min_margin_pct: float = 0.0
    max_uncertainty: float = 0.5
    require_stop_loss: bool = True
    require_take_profit: bool = True
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class BDIIntention(BaseModel):
    """Intención del agente: plan concreto antes del compromiso."""

    intention_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    is_committed: bool = False
    planned_action: str = "HOLD"  # BUY, SELL, HOLD, ESCALATE_HUMAN
    planned_params: Dict[str, Any] = Field(default_factory=dict)
    actions: List[AgentAction] = Field(default_factory=list)
    justification: str = ""
    survival_score: float = 0.0
    status: str = "draft"  # draft, distilled, committed, rejected
    cot_trace: List[CoTStep] = Field(default_factory=list)
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class JuiceVerdict(BaseModel):
    """Veredicto del filtro adversarial Juice."""

    verdict_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    approved: bool = False
    survival_score: float = 0.0
    issues: List[str] = Field(default_factory=list)
    corrected_intention: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class BDIState(BaseModel):
    """Estado completo BDI del agente para auditoría y API."""

    bdi_state_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    beliefs: Dict[str, Any] = Field(default_factory=dict)
    desires: Dict[str, Any] = Field(default_factory=dict)
    draft_intention: Optional[Dict[str, Any]] = None
    juice_verdict: Optional[Dict[str, Any]] = None
    committed_intention: Optional[Dict[str, Any]] = None
    cot_trace: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
