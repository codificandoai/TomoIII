"""Configuración centralizada para UC-264 - Model-Based Multi-Agent Travel Planner."""
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
    seed: int = _env_int("UC264_WORLD_SEED", 42)
    simulated_latency_ms: int = _env_int("UC264_SIMULATED_LATENCY_MS", 0)
    default_currency: str = _env_str("UC264_DEFAULT_CURRENCY", "USD")


@dataclass
class PredictorConfig:
    url: str = _env_str(
        "UC264_PREDICTOR_URL",
        "https://flight-delays-v10p.onrender.com/predict",
    )
    timeout: int = _env_int("UC264_PREDICTOR_TIMEOUT", 10)
    high_delay_threshold: float = _env_float("UC264_HIGH_DELAY_THRESHOLD", 0.5)


@dataclass
class ModelConfig:
    """Configuración del World Model y planificación."""

    num_candidate_plans: int = _env_int("UC264_NUM_CANDIDATE_PLANS", 16)
    mc_simulations_per_plan: int = _env_int("UC264_MC_SIMULATIONS_PER_PLAN", 200)
    mc_budget_samples: int = _env_int("UC264_MC_BUDGET_SAMPLES", 50)
    horizon: int = _env_int("UC264_HORIZON", 5)
    ucb_constant: float = _env_float("UC264_UCB_CONSTANT", 1.414)
    risk_aversion: float = _env_float("UC264_RISK_AVERSION", 0.5)
    cost_weight: float = _env_float("UC264_COST_WEIGHT", 0.3)
    time_weight: float = _env_float("UC264_TIME_WEIGHT", 0.2)
    comfort_weight: float = _env_float("UC264_COMFORT_WEIGHT", 0.2)
    success_weight: float = _env_float("UC264_SUCCESS_WEIGHT", 0.3)
    learning_rate: float = _env_float("UC264_WORLD_MODEL_LR", 0.2)


@dataclass
class AgentConfig:
    max_retries: int = _env_int("UC264_MAX_RETRIES", 3)
    require_confirmation_irreversible: bool = _env_bool(
        "UC264_REQUIRE_CONFIRMATION_IRREVERSIBLE", True
    )
    enable_prompt_injection_check: bool = _env_bool(
        "UC264_ENABLE_PROMPT_INJECTION_CHECK", True
    )
    enable_pii_redaction: bool = _env_bool("UC264_ENABLE_PII_REDACTION", True)


@dataclass
class AppConfig:
    world: WorldConfig = field(default_factory=WorldConfig)
    predictor: PredictorConfig = field(default_factory=PredictorConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    port: int = _env_int("UC264_PORT", 5264)


def get_config() -> AppConfig:
    return AppConfig()


CONFIG = get_config()
