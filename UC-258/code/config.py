"""Configuración centralizada del meta-framework de agentes adaptativos UC-258."""
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
class EnvironmentConfig:
    """Configuración de entornos simulados."""

    chess_use_python_chess: bool = _env_bool("UC258_CHESS_USE_PYTHON_CHESS", False)
    stock_volatility: float = _env_float("UC258_STOCK_VOLATILITY", 0.02)
    stock_hidden_event_prob: float = _env_float("UC258_STOCK_HIDDEN_EVENT_PROB", 0.2)
    travel_simulated_latency_ms: int = _env_int("UC258_TRAVEL_SIMULATED_LATENCY_MS", 100)
    travel_currency_base: str = _env_str("UC258_TRAVEL_CURRENCY_BASE", "USD")


@dataclass
class AgentConfig:
    """Configuración del agente adaptativo."""

    max_planning_steps: int = _env_int("UC258_MAX_PLANNING_STEPS", 20)
    confidence_threshold: float = _env_float("UC258_CONFIDENCE_THRESHOLD", 0.7)
    require_confirmation_irreversible: bool = _env_bool(
        "UC258_REQUIRE_CONFIRMATION_IRREVERSIBLE", True
    )
    enable_prompt_injection_check: bool = _env_bool(
        "UC258_ENABLE_PROMPT_INJECTION_CHECK", True
    )
    enable_pii_redaction: bool = _env_bool("UC258_ENABLE_PII_REDACTION", True)
    max_iterations: int = _env_int("UC258_MAX_ITERATIONS", 50)


@dataclass
class LLMConfig:
    """Configuración de LLM opcional para estrategias basadas en lenguaje."""

    provider: str = _env_str("UC258_LLM_PROVIDER", "stub")
    model: str = _env_str("UC258_LLM_MODEL", "stub")
    api_key: str = _env_str("UC258_OPENAI_API_KEY", "")
    temperature: float = _env_float("UC258_LLM_TEMPERATURE", 0.0)


@dataclass
class AppConfig:
    """Configuración global."""

    env: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    port: int = _env_int("UC258_PORT", 5258)


CONFIG = AppConfig()
