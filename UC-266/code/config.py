"""Configuración centralizada para UC-266 - Agente Resiliente y Robusto."""
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
    seed: int = _env_int("UC266_WORLD_SEED", 42)
    simulated_latency_ms: int = _env_int("UC266_SIMULATED_LATENCY_MS", 0)
    default_currency: str = _env_str("UC266_DEFAULT_CURRENCY", "USD")
    partial_observability: bool = _env_bool("UC266_PARTIAL_OBSERVABILITY", True)
    observation_noise: float = _env_float("UC266_OBSERVATION_NOISE", 0.1)
    change_event_prob: float = _env_float("UC266_CHANGE_EVENT_PROB", 0.05)


@dataclass
class PredictorConfig:
    url: str = _env_str(
        "UC266_PREDICTOR_URL",
        "https://flight-delays-v10p.onrender.com/predict",
    )
    timeout: int = _env_int("UC266_PREDICTOR_TIMEOUT", 10)
    high_delay_threshold: float = _env_float("UC266_HIGH_DELAY_THRESHOLD", 0.5)


@dataclass
class TorchConfig:
    """Hiperparámetros de los modelos de PyTorch."""

    device: str = _env_str("UC266_TORCH_DEVICE", "cpu")
    epochs: int = _env_int("UC266_TORCH_EPOCHS", 80)
    lr: float = _env_float("UC266_TORCH_LR", 1e-3)
    batch_size: int = _env_int("UC266_TORCH_BATCH_SIZE", 32)
    hidden_dim: int = _env_int("UC266_TORCH_HIDDEN_DIM", 64)
    dropout: float = _env_float("UC266_TORCH_DROPOUT", 0.1)


@dataclass
class ProbabilisticModelConfig:
    """Configuración de modelos probabilísticos y aprendizaje (PyTorch/GPyTorch)."""

    model_type: str = _env_str("UC266_WORLD_MODEL_TYPE", "neural")  # neural | gp | hybrid
    min_samples_to_train: int = _env_int("UC266_MIN_SAMPLES_TO_TRAIN", 10)
    retrain_after: int = _env_int("UC266_RETRAIN_AFTER", 10)
    uncertainty_retrain_threshold: float = _env_float("UC266_UNCERTAINTY_RETRAIN_THRESHOLD", 0.5)
    prediction_error_retrain_threshold: float = _env_float("UC266_PREDICTION_ERROR_RETRAIN_THRESHOLD", 0.3)
    prediction_error_window: int = _env_int("UC266_PREDICTION_ERROR_WINDOW", 20)
    embedding_dim: int = _env_int("UC266_EMBEDDING_DIM", 16)
    belief_dim: int = _env_int("UC266_BELIEF_DIM", 6)
    # Producción: PyTorch. Si GPyTorch no está instalado, el GP cae en un GP simple con torch.
    gp_kernel: str = _env_str("UC266_GP_KERNEL", "rbf")
    gp_alpha: float = _env_float("UC266_GP_ALPHA", 1e-2)
    torch: TorchConfig = field(default_factory=TorchConfig)


@dataclass
class MCTSConfig:
    """Configuración del MCTS optimizado sobre el espacio de acciones."""

    num_iterations: int = _env_int("UC266_MCTS_ITERATIONS", 200)
    ucb_constant: float = _env_float("UC266_MCTS_UCB_CONSTANT", 1.414)
    max_depth: int = _env_int("UC266_MCTS_MAX_DEPTH", 5)
    rollout_count: int = _env_int("UC266_MCTS_ROLLOUT_COUNT", 10)
    action_budget: int = _env_int("UC266_MCTS_ACTION_BUDGET", 6)
    enable_action_embedding: bool = _env_bool("UC266_MCTS_ACTION_EMBEDDING", True)
    enable_persistent_tree: bool = _env_bool("UC266_MCTS_ENABLE_PERSISTENT_TREE", True)
    persistent_tree_path: str = _env_str("UC266_MCTS_PERSISTENT_TREE_PATH", "")
    tree_similarity_threshold: float = _env_float("UC266_MCTS_TREE_SIMILARITY_THRESHOLD", 0.9)


@dataclass
class VectorStoreConfig:
    """Backends de vector store: simple (fallback), faiss o pgvector."""

    backend: str = _env_str("UC266_VECTOR_BACKEND", "simple")  # simple | faiss | pgvector
    path: str = _env_str("UC266_VECTOR_STORE_PATH", "")
    dim: int = _env_int("UC266_VECTOR_DIM", 16)
    # Configuración pgvector (solo se usa si backend == "pgvector")
    pg_host: str = _env_str("UC266_PG_HOST", "localhost")
    pg_port: int = _env_int("UC266_PG_PORT", 5432)
    pg_user: str = _env_str("UC266_PG_USER", "")
    pg_password: str = _env_str("UC266_PG_PASSWORD", "")
    pg_db: str = _env_str("UC266_PG_DB", "")
    pg_table: str = _env_str("UC266_PG_TABLE", "uc266_vectors")


@dataclass
class StorageConfig:
    """Persistencia relacional (SQLite) y vectorial."""

    sqlite_path: str = _env_str("UC266_SQLITE_PATH", "")
    vector: VectorStoreConfig = field(default_factory=VectorStoreConfig)


@dataclass
class ResilienceConfig:
    """Configuración del motor de resiliencia robusta."""

    enable: bool = _env_bool("UC266_RESILIENCE_ENABLE", True)
    backup_plan_count: int = _env_int("UC266_BACKUP_PLAN_COUNT", 3)
    max_recovery_attempts: int = _env_int("UC266_MAX_RECOVERY_ATTEMPTS", 3)
    change_detection_threshold: float = _env_float("UC266_CHANGE_DETECTION_THRESHOLD", 0.3)
    drift_threshold: float = _env_float("UC266_DRIFT_THRESHOLD", 0.25)
    replan_after_failure: bool = _env_bool("UC266_REPLAN_AFTER_FAILURE", True)
    enable_self_correction: bool = _env_bool("UC266_ENABLE_SELF_CORRECTION", True)
    recovery_strategy: str = _env_str("UC266_RECOVERY_STRATEGY", "replan")


@dataclass
class ModelConfig:
    """Configuración del World Model y planificación."""

    num_candidate_plans: int = _env_int("UC266_NUM_CANDIDATE_PLANS", 16)
    mc_simulations_per_plan: int = _env_int("UC266_MC_SIMULATIONS_PER_PLAN", 100)
    horizon: int = _env_int("UC266_HORIZON", 5)
    risk_aversion: float = _env_float("UC266_RISK_AVERSION", 0.5)
    cost_weight: float = _env_float("UC266_COST_WEIGHT", 0.3)
    time_weight: float = _env_float("UC266_TIME_WEIGHT", 0.2)
    comfort_weight: float = _env_float("UC266_COMFORT_WEIGHT", 0.2)
    success_weight: float = _env_float("UC266_SUCCESS_WEIGHT", 0.3)
    learning_rate: float = _env_float("UC266_WORLD_MODEL_LR", 0.2)
    probabilistic: ProbabilisticModelConfig = field(default_factory=ProbabilisticModelConfig)
    mcts: MCTSConfig = field(default_factory=MCTSConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    resilience: ResilienceConfig = field(default_factory=ResilienceConfig)


@dataclass
class AgentConfig:
    max_retries: int = _env_int("UC266_MAX_RETRIES", 3)
    require_confirmation_irreversible: bool = _env_bool(
        "UC266_REQUIRE_CONFIRMATION_IRREVERSIBLE", True
    )
    enable_prompt_injection_check: bool = _env_bool(
        "UC266_ENABLE_PROMPT_INJECTION_CHECK", True
    )
    enable_pii_redaction: bool = _env_bool("UC266_ENABLE_PII_REDACTION", True)


@dataclass
class AppConfig:
    world: WorldConfig = field(default_factory=WorldConfig)
    predictor: PredictorConfig = field(default_factory=PredictorConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    resilience: ResilienceConfig = field(default_factory=ResilienceConfig)
    port: int = _env_int("UC266_PORT", 5266)
    flight_delays_model_path: str = _env_str(
        "UC266_FLIGHT_DELAYS_MODEL_PATH",
        os.path.join(os.path.dirname(__file__), "flight-delays", "challenge", "model.pkl"),
    )


def get_config() -> AppConfig:
    return AppConfig()


CONFIG = get_config()
