"""Configuración centralizada para UC-259 - Agentic Flight Planner."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, List


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


def _env_list(name: str, default: List[str]) -> List[str]:
    val = os.getenv(name)
    if not val:
        return list(default)
    return [x.strip() for x in val.split(",") if x.strip()]


@dataclass
class WorldConfig:
    """Configuración del simulador externo."""

    seed: int = _env_int("UC259_WORLD_SEED", 42)
    simulated_latency_ms: int = _env_int("UC259_SIMULATED_LATENCY_MS", 50)
    random_event_prob: float = _env_float("UC259_RANDOM_EVENT_PROB", 0.0)
    default_currency: str = _env_str("UC259_DEFAULT_CURRENCY", "USD")


@dataclass
class AgentConfig:
    """Configuración del agente."""

    max_retries: int = _env_int("UC259_MAX_RETRIES", 3)
    max_iterations: int = _env_int("UC259_MAX_ITERATIONS", 50)
    confidence_threshold: float = _env_float("UC259_CONFIDENCE_THRESHOLD", 0.7)
    require_confirmation_irreversible: bool = _env_bool(
        "UC259_REQUIRE_CONFIRMATION_IRREVERSIBLE", True
    )
    enable_prompt_injection_check: bool = _env_bool(
        "UC259_ENABLE_PROMPT_INJECTION_CHECK", True
    )
    enable_pii_redaction: bool = _env_bool("UC259_ENABLE_PII_REDACTION", True)


@dataclass
class AppConfig:
    """Configuración global de la aplicación."""

    world: WorldConfig = field(default_factory=WorldConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    port: int = _env_int("UC259_PORT", 5259)


def get_config() -> AppConfig:
    """Devuelve una instancia fresca de configuración."""
    return AppConfig()


CONFIG = get_config()
