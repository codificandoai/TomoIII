"""Configuración centralizada del sistema de agentes de viajes UC-257."""
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


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class LLMConfig:
    """Configuración del modelo LLM (OpenAI / Azure)."""

    provider: str = _env_str("UC257_LLM_PROVIDER", "stub")
    # openai | azure | stub
    model: str = _env_str("UC257_LLM_MODEL", "gpt-4o-mini")
    api_key: str = _env_str("UC257_OPENAI_API_KEY", "")
    api_base: str = _env_str("UC257_OPENAI_API_BASE", "")
    api_version: str = _env_str("UC257_OPENAI_API_VERSION", "2024-06-01")
    temperature: float = 0.0


@dataclass
class FrameworkConfig:
    """Habilitar frameworks reales vs simuladores deterministas."""

    use_semantic_kernel: bool = _env_bool("UC257_USE_SEMANTIC_KERNEL", False)
    use_autogen: bool = _env_bool("UC257_USE_AUTOGEN", False)
    autogen_max_turns: int = _env_int("UC257_AUTOGEN_MAX_TURNS", 10)


@dataclass
class AgentConfig:
    """Parámetros del orquestador de agentes."""

    max_iterations: int = _env_int("UC257_AGENT_MAX_ITERATIONS", 20)
    rebooking_enabled: bool = _env_bool("UC257_REBOOKING_ENABLED", True)
    monitoring_interval_seconds: int = _env_int(
        "UC257_MONITORING_INTERVAL_SECONDS", 5
    )
    require_human_confirmation: bool = _env_bool(
        "UC257_REQUIRE_HUMAN_CONFIRMATION", False
    )


@dataclass
class APICard:
    """Card view para documentación de entrada/salida."""

    endpoint: str
    description: str
    parameters: List[dict] = field(default_factory=list)
    fields: List[dict] = field(default_factory=list)


@dataclass
class AppConfig:
    """Configuración global."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    frameworks: FrameworkConfig = field(default_factory=FrameworkConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    port: int = _env_int("UC257_PORT", 5257)


CONFIG = AppConfig()
