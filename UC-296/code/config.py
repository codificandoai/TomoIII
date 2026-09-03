"""Configuración centralizada para UC-292 - Sistema Multi-Agente de Trading."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class MarketConfig:
    """Parámetros del feed de mercado."""

    default_symbols: list[str] = field(default_factory=lambda: ["AAPL"])
    history_window: int = _env_int("UC292_HISTORY_WINDOW", 50)
    resample_interval_ms: int = _env_int("UC292_RESAMPLE_MS", 1)
    outlier_z: float = _env_float("UC292_OUTLIER_Z", 4.0)
    seed: int = _env_int("UC292_MARKET_SEED", 42)


@dataclass
class FeatureConfig:
    """Ventanas de indicadores técnicos."""

    sma_fast: int = _env_int("UC292_SMA_FAST", 20)
    sma_slow: int = _env_int("UC292_SMA_SLOW", 50)
    rsi_window: int = _env_int("UC292_RSI_WINDOW", 14)
    atr_window: int = _env_int("UC292_ATR_WINDOW", 14)
    bollinger_window: int = _env_int("UC292_BB_WINDOW", 20)
    macd_fast: int = _env_int("UC292_MACD_FAST", 12)
    macd_slow: int = _env_int("UC292_MACD_SLOW", 26)
    macd_signal: int = _env_int("UC292_MACD_SIGNAL", 9)


@dataclass
class RiskConfig:
    """Límites de riesgo operativo."""

    max_position_pct: float = _env_float("UC292_MAX_POSITION_PCT", 0.2)
    max_drawdown_pct: float = _env_float("UC292_MAX_DRAWDOWN_PCT", 0.05)
    stop_loss_pct: float = _env_float("UC292_STOP_LOSS_PCT", 0.02)
    take_profit_pct: float = _env_float("UC292_TAKE_PROFIT_PCT", 0.04)
    max_trade_notional: float = _env_float("UC292_MAX_TRADE_NOTIONAL", 100_000.0)
    max_orders_per_min: int = _env_int("UC292_MAX_ORDERS_PER_MIN", 10)
    circuit_breaker_failures: int = _env_int("UC292_CIRCUIT_BREAKER_FAILURES", 3)
    max_price_jump_std: float = _env_float("UC292_MAX_PRICE_JUMP_STD", 5.0)
    min_signal_confidence: float = _env_float("UC292_MIN_SIGNAL_CONFIDENCE", 0.5)


@dataclass
class ProbabilisticModelConfig:
    """Configuración del modelo probabilístico de transiciones."""

    model_type: str = _env_str("UC292_WORLD_MODEL_TYPE", "neural")  # neural | gp | hybrid
    min_samples_to_train: int = _env_int("UC292_MIN_SAMPLES_TO_TRAIN", 5)
    retrain_after: int = _env_int("UC292_RETRAIN_AFTER", 10)
    uncertainty_retrain_threshold: float = _env_float("UC292_UNCERTAINTY_RETRAIN_THRESHOLD", 0.5)
    prediction_error_retrain_threshold: float = _env_float("UC292_PREDICTION_ERROR_RETRAIN_THRESHOLD", 0.3)
    prediction_error_window: int = _env_int("UC292_PREDICTION_ERROR_WINDOW", 20)
    embedding_dim: int = _env_int("UC292_EMBEDDING_DIM", 16)
    hidden_layers: tuple = field(default_factory=lambda: (64, 32))
    max_iter: int = _env_int("UC292_NN_MAX_ITER", 500)
    gp_kernel: str = _env_str("UC292_GP_KERNEL", "rbf")
    gp_alpha: float = _env_float("UC292_GP_ALPHA", 1e-10)


@dataclass
class MCTSConfig:
    """Configuración de MCTS sobre acciones de trading."""

    num_iterations: int = _env_int("UC292_MCTS_ITERATIONS", 200)
    ucb_constant: float = _env_float("UC292_MCTS_UCB_CONSTANT", 1.414)
    max_depth: int = _env_int("UC292_MCTS_MAX_DEPTH", 5)
    rollout_count: int = _env_int("UC292_MCTS_ROLLOUT_COUNT", 10)
    enable_persistent_tree: bool = _env_bool("UC292_MCTS_ENABLE_PERSISTENT_TREE", True)
    persistent_tree_path: str = _env_str("UC292_MCTS_PERSISTENT_TREE_PATH", "")
    tree_similarity_threshold: float = _env_float("UC292_MCTS_TREE_SIMILARITY_THRESHOLD", 0.9)


@dataclass
class StorageConfig:
    """Persistencia: SQLite y vector store."""

    sqlite_path: str = _env_str("UC292_SQLITE_PATH", "")
    vector_store_path: str = _env_str("UC292_VECTOR_STORE_PATH", "")
    use_vector_store: bool = _env_bool("UC292_USE_VECTOR_STORE", True)
    vector_dim: int = _env_int("UC292_VECTOR_DIM", 16)


@dataclass
class JuiceConfig:
    """Integración con Juice Agents para validación de inferencias."""

    enabled: bool = _env_bool("UC292_JUICE_ENABLED", False)
    url: str = _env_str("UC292_JUICE_URL", "")
    timeout: int = _env_int("UC292_JUICE_TIMEOUT", 10)
    agents: list[str] = field(default_factory=lambda: ["technical", "sentiment", "risk", "fundamental"])


@dataclass
class MCPConfig:
    """Configuración del registro de herramientas MCP."""

    enable_server: bool = _env_bool("UC292_MCP_ENABLE", True)


@dataclass
class AgentConfig:
    """Comportamiento del orquestador de agentes."""

    max_retries: int = _env_int("UC292_MAX_RETRIES", 3)
    require_confirmation: bool = _env_bool("UC292_REQUIRE_CONFIRMATION", True)
    enable_prompt_injection_check: bool = _env_bool("UC292_ENABLE_PROMPT_INJECTION_CHECK", True)


@dataclass
class ModelConfig:
    """Configuración del world model y planificación."""

    num_candidate_strategies: int = _env_int("UC292_NUM_CANDIDATE_STRATEGIES", 16)
    mc_simulations_per_strategy: int = _env_int("UC292_MC_SIMULATIONS_PER_STRATEGY", 100)
    horizon: int = _env_int("UC292_HORIZON", 5)
    risk_aversion: float = _env_float("UC292_RISK_AVERSION", 0.5)
    return_weight: float = _env_float("UC292_RETURN_WEIGHT", 0.5)
    risk_weight: float = _env_float("UC292_RISK_WEIGHT", 0.3)
    alignment_weight: float = _env_float("UC292_ALIGNMENT_WEIGHT", 0.2)
    learning_rate: float = _env_float("UC292_LEARNING_RATE", 0.2)
    probabilistic: ProbabilisticModelConfig = field(default_factory=ProbabilisticModelConfig)
    mcts: MCTSConfig = field(default_factory=MCTSConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)


@dataclass
class AppConfig:
    """Configuración global de UC-292."""

    market: MarketConfig = field(default_factory=MarketConfig)
    features: FeatureConfig = field(default_factory=FeatureConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    juice: JuiceConfig = field(default_factory=JuiceConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    port: int = _env_int("UC292_PORT", 5292)


def get_config() -> AppConfig:
    return AppConfig()


CONFIG = get_config()
