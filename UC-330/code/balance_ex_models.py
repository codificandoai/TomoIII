"""
UC-330 — Modelos de datos para Exploitation–Exploration Governance.

Define configuración, decisiones, métricas y resultados del balance
exploración-explotación.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import time
import uuid


class DecisionMode(Enum):
    """Modos de decisión del controlador de exploración-explotación."""
    EXPLOIT = "exploit"
    SANDBOX = "sandbox"
    ESCALATE = "escalate"


class ExplorationStrategy(Enum):
    """Estrategias internas de exploración."""
    RANDOM = "random"
    UCB = "ucb"
    DIRECTED = "directed"
    CURIOSITY = "curiosity"


@dataclass
class BalanceExConfig:
    """Configuración del balance exploración-explotación."""
    epsilon_initial: float = 0.30
    epsilon_min: float = 0.01
    decay_rate: float = 0.995
    change_window: int = 100
    change_threshold: float = 0.15
    alpha_learning: float = 0.10
    gamma_discount: float = 0.95
    exploration_budget: Optional[float] = None
    horizon: Optional[int] = None
    min_trials: int = 5
    info_bonus: float = 0.5
    risk_weight: float = 0.3
    ucb_kappa: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "epsilon_initial": self.epsilon_initial,
            "epsilon_min": self.epsilon_min,
            "decay_rate": self.decay_rate,
            "change_window": self.change_window,
            "change_threshold": self.change_threshold,
            "alpha_learning": self.alpha_learning,
            "gamma_discount": self.gamma_discount,
            "exploration_budget": self.exploration_budget,
            "horizon": self.horizon,
            "min_trials": self.min_trials,
            "info_bonus": self.info_bonus,
            "risk_weight": self.risk_weight,
            "ucb_kappa": self.ucb_kappa,
        }


@dataclass
class ContextSnapshot:
    """Instantánea de contexto para decisiones."""
    context_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    features: Dict[str, float] = field(default_factory=dict)
    domain: str = "default"
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def vector(self, keys: Optional[List[str]] = None) -> List[float]:
        """Retorna vector de características ordenado."""
        if keys is None:
            keys = sorted(self.features.keys())
        return [self.features.get(k, 0.0) for k in keys]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context_id": self.context_id,
            "features": self.features,
            "domain": self.domain,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ActionRecord:
    """Registro de una acción ejecutada y su resultado."""
    action_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    action: str = ""
    context_id: str = ""
    mode: DecisionMode = DecisionMode.EXPLOIT
    strategy: ExplorationStrategy = ExplorationStrategy.RANDOM
    reward: float = 0.0
    risk: float = 0.0
    cost: float = 0.0
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action": self.action,
            "context_id": self.context_id,
            "mode": self.mode.value,
            "strategy": self.strategy.value,
            "reward": round(self.reward, 6),
            "risk": round(self.risk, 6),
            "cost": round(self.cost, 6),
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class Decision:
    """Decisión emitida por el controlador de explotación-exploración."""
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    mode: DecisionMode = DecisionMode.EXPLOIT
    strategy: ExplorationStrategy = ExplorationStrategy.RANDOM
    action: str = ""
    epsilon: float = 0.0
    uncertainty: float = 0.0
    risk_score: float = 0.0
    justification: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "mode": self.mode.value,
            "strategy": self.strategy.value,
            "action": self.action,
            "epsilon": round(self.epsilon, 4),
            "uncertainty": round(self.uncertainty, 4),
            "risk_score": round(self.risk_score, 4),
            "justification": self.justification,
            "metadata": self.metadata,
        }


@dataclass
class BalanceMetrics:
    """Métricas de balance exploración-explotación."""
    total_steps: int = 0
    exploit_steps: int = 0
    sandbox_steps: int = 0
    escalate_steps: int = 0
    exploration_rate: float = 0.0
    success_rate: float = 0.0
    diversity: float = 0.0
    regret: float = 0.0
    avg_reward: float = 0.0
    cumulative_reward: float = 0.0
    change_detected: bool = False
    budget_remaining: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_steps": self.total_steps,
            "exploit_steps": self.exploit_steps,
            "sandbox_steps": self.sandbox_steps,
            "escalate_steps": self.escalate_steps,
            "exploration_rate": round(self.exploration_rate, 4),
            "success_rate": round(self.success_rate, 4),
            "diversity": round(self.diversity, 4),
            "regret": round(self.regret, 4),
            "avg_reward": round(self.avg_reward, 4),
            "cumulative_reward": round(self.cumulative_reward, 4),
            "change_detected": self.change_detected,
            "budget_remaining": self.budget_remaining,
        }


@dataclass
class BalanceExResult:
    """Resultado completo del controlador."""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision: Optional[Decision] = None
    metrics: BalanceMetrics = field(default_factory=BalanceMetrics)
    history: List[ActionRecord] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "decision": self.decision.to_dict() if self.decision else None,
            "metrics": self.metrics.to_dict(),
            "history": [h.to_dict() for h in self.history],
            "recommendations": self.recommendations,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp,
        }
