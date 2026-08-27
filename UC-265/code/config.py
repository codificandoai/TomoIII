"""Configuración centralizada para UC-265 - Probabilistic Model-Based Planner."""
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
class WorldConfig:
    seed: int = _env_int("UC265_WORLD_SEED", 42)
    simulated_latency_ms: int = _env_int("UC265_SIMULATED_LATENCY_MS", 0)
    default_currency: str = _env_str("UC265_DEFAULT_CURRENCY", "USD")
    partial_observability: bool = _env_bool("UC265_PARTIAL_OBSERVABILITY", True)
    observation_noise: float = _env_float("UC265_OBSERVATION_NOISE", 0.1)


@dataclass
class PredictorConfig:
    url: str = _env_str(
        "UC265_PREDICTOR_URL",
        "https://flight-delays-v10p.onrender.com/predict",
    )
    timeout: int = _env_int("UC265_PREDICTOR_TIMEOUT", 10)
    high_delay_threshold: float = _env_float("UC265_HIGH_DELAY_THRESHOLD", 0.5)


@dataclass
class ProbabilisticModelConfig:
    """Configuración de modelos probabilísticos y aprendizaje."""

    model_type: str = _env_str("UC265_WORLD_MODEL_TYPE", "neural")  # neural | gp | hybrid
    min_samples_to_train: int = _env_int("UC265_MIN_SAMPLES_TO_TRAIN", 5)
    retrain_after: int = _env_int("UC265_RETRAIN_AFTER", 10)
    embedding_dim: int = _env_int("UC265_EMBEDDING_DIM", 16)
    # Neural network
    hidden_layers: tuple = field(default_factory=lambda: (64, 32))
    max_iter: int = _env_int("UC265_NN_MAX_ITER", 500)
    # Gaussian process
    gp_kernel: str = _env_str("UC265_GP_KERNEL", "rbf")
    gp_alpha: float = _env_float("UC265_GP_ALPHA", 1e-10)


@dataclass
class MCTSConfig:
    """Configuración del MCTS sobre el espacio de acciones."""

    num_iterations: int = _env_int("UC265_MCTS_ITERATIONS", 200)
    ucb_constant: float = _env_float("UC265_MCTS_UCB_CONSTANT", 1.414)
    max_depth: int = _env_int("UC265_MCTS_MAX_DEPTH", 5)
    rollout_count: int = _env_int("UC265_MCTS_ROLLOUT_COUNT", 10)


@dataclass
class StorageConfig:
    """Persistencia: SQLite y vector store."""

    sqlite_path: str = _env_str("UC265_SQLITE_PATH", "")
    vector_store_path: str = _env_str("UC265_VECTOR_STORE_PATH", "")
    use_vector_store: bool = _env_bool("UC265_USE_VECTOR_STORE", True)
    vector_dim: int = _env_int("UC265_VECTOR_DIM", 16)


@dataclass
class ModelConfig:
    """Configuración del World Model y planificación."""

    num_candidate_plans: int = _env_int("UC265_NUM_CANDIDATE_PLANS", 16)
    mc_simulations_per_plan: int = _env_int("UC265_MC_SIMULATIONS_PER_PLAN", 100)
    horizon: int = _env_int("UC265_HORIZON", 5)
    risk_aversion: float = _env_float("UC265_RISK_AVERSION", 0.5)
    cost_weight: float = _env_float("UC265_COST_WEIGHT", 0.3)
    time_weight: float = _env_float("UC265_TIME_WEIGHT", 0.2)
    comfort_weight: float = _env_float("UC265_COMFORT_WEIGHT", 0.2)
    success_weight: float = _env_float("UC265_SUCCESS_WEIGHT", 0.3)
    learning_rate: float = _env_float("UC265_WORLD_MODEL_LR", 0.2)
    probabilistic: ProbabilisticModelConfig = field(default_factory=ProbabilisticModelConfig)
    mcts: MCTSConfig = field(default_factory=MCTSConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)


@dataclass
class AgentConfig:
    max_retries: int = _env_int("UC265_MAX_RETRIES", 3)
    require_confirmation_irreversible: bool = _env_bool(
        "UC265_REQUIRE_CONFIRMATION_IRREVERSIBLE", True
    )
    enable_prompt_injection_check: bool = _env_bool(
        "UC265_ENABLE_PROMPT_INJECTION_CHECK", True
    )
    enable_pii_redaction: bool = _env_bool("UC265_ENABLE_PII_REDACTION", True)


@dataclass
class AppConfig:
    world: WorldConfig = field(default_factory=WorldConfig)
    predictor: PredictorConfig = field(default_factory=PredictorConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    port: int = _env_int("UC265_PORT", 5265)


def get_config() -> AppConfig:
    return AppConfig()


CONFIG = get_config()
