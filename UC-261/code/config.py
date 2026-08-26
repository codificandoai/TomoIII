"""Configuración centralizada para UC-261 - Agente adaptativo con memoria de patrones."""
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
    seed: int = _env_int("UC261_WORLD_SEED", 42)
    simulated_latency_ms: int = _env_int("UC261_SIMULATED_LATENCY_MS", 0)
    random_event_prob: float = _env_float("UC261_RANDOM_EVENT_PROB", 0.0)
    default_currency: str = _env_str("UC261_DEFAULT_CURRENCY", "USD")


@dataclass
class PredictorConfig:
    url: str = _env_str(
        "UC261_PREDICTOR_URL",
        "https://flight-delays-v10p.onrender.com/predict",
    )
    timeout: int = _env_int("UC261_PREDICTOR_TIMEOUT", 10)
    high_delay_threshold: float = _env_float("UC261_HIGH_DELAY_THRESHOLD", 0.5)


@dataclass
class MemoryConfig:
    path: str = _env_str("UC261_MEMORY_PATH", "")
    pattern_match_threshold: float = _env_float("UC261_PATTERN_MATCH_THRESHOLD", 0.6)
    auto_cost_threshold: float = _env_float("UC261_AUTO_COST_THRESHOLD", 200.0)


@dataclass
class CheckpointConfig:
    path: str = _env_str("UC261_CHECKPOINT_PATH", "")
    use_memory: bool = _env_bool("UC261_USE_MEMORY_CHECKPOINTER", True)


@dataclass
class AgentConfig:
    max_retries: int = _env_int("UC261_MAX_RETRIES", 3)
    max_iterations: int = _env_int("UC261_MAX_ITERATIONS", 50)
    confidence_threshold: float = _env_float("UC261_CONFIDENCE_THRESHOLD", 0.7)
    require_confirmation_irreversible: bool = _env_bool(
        "UC261_REQUIRE_CONFIRMATION_IRREVERSIBLE", True
    )
    enable_prompt_injection_check: bool = _env_bool(
        "UC261_ENABLE_PROMPT_INJECTION_CHECK", True
    )
    enable_pii_redaction: bool = _env_bool("UC261_ENABLE_PII_REDACTION", True)
    enable_learning: bool = _env_bool("UC261_ENABLE_LEARNING", True)


@dataclass
class AppConfig:
    world: WorldConfig = field(default_factory=WorldConfig)
    predictor: PredictorConfig = field(default_factory=PredictorConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    checkpoint: CheckpointConfig = field(default_factory=CheckpointConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    port: int = _env_int("UC261_PORT", 5261)


def get_config() -> AppConfig:
    return AppConfig()


CONFIG = get_config()
