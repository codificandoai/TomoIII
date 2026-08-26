"""Configuración centralizada para UC-260 - Agente BDI de viajes."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


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
    """Configuración del simulador externo."""

    seed: int = _env_int("UC260_WORLD_SEED", 42)
    simulated_latency_ms: int = _env_int("UC260_SIMULATED_LATENCY_MS", 50)
    random_event_prob: float = _env_float("UC260_RANDOM_EVENT_PROB", 0.0)
    default_currency: str = _env_str("UC260_DEFAULT_CURRENCY", "USD")


@dataclass
class PredictorConfig:
    """Configuración del predictor de retrasos."""

    url: str = _env_str(
        "UC260_PREDICTOR_URL",
        "https://flight-delays-v10p.onrender.com/predict",
    )
    timeout: int = _env_int("UC260_PREDICTOR_TIMEOUT", 10)
    high_delay_threshold: float = _env_float("UC260_HIGH_DELAY_THRESHOLD", 0.5)


@dataclass
class AgentConfig:
    """Configuración del agente BDI."""

    max_retries: int = _env_int("UC260_MAX_RETRIES", 3)
    max_iterations: int = _env_int("UC260_MAX_ITERATIONS", 50)
    confidence_threshold: float = _env_float("UC260_CONFIDENCE_THRESHOLD", 0.7)
    require_confirmation_irreversible: bool = _env_bool(
        "UC260_REQUIRE_CONFIRMATION_IRREVERSIBLE", True
    )
    enable_prompt_injection_check: bool = _env_bool(
        "UC260_ENABLE_PROMPT_INJECTION_CHECK", True
    )
    enable_pii_redaction: bool = _env_bool("UC260_ENABLE_PII_REDACTION", True)
    enable_learning: bool = _env_bool("UC260_ENABLE_LEARNING", True)


@dataclass
class AppConfig:
    """Configuración global."""

    world: WorldConfig = field(default_factory=WorldConfig)
    predictor: PredictorConfig = field(default_factory=PredictorConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    port: int = _env_int("UC260_PORT", 5260)


def get_config() -> AppConfig:
    return AppConfig()


CONFIG = get_config()
