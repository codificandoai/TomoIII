"""Configuración centralizada para UC-268 - Comunicación segura A2A entre agentes."""
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


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class SecurityConfig:
    jwt_secret: str = _env_str("UC268_JWT_SECRET", "dev-secret-do-not-use-in-production")
    jwt_algorithm: str = _env_str("UC268_JWT_ALGORITHM", "HS256")
    token_ttl_minutes: int = _env_int("UC268_TOKEN_TTL_MINUTES", 60)
    require_tls: bool = _env_bool("UC268_REQUIRE_TLS", False)
    min_tls_version: str = _env_str("UC268_MIN_TLS_VERSION", "1.2")
    api_keys: list[str] = field(default_factory=lambda: ["dev-api-key"])

    def __post_init__(self) -> None:
        keys_env = os.getenv("UC268_API_KEYS")
        if keys_env:
            self.api_keys = [k.strip() for k in keys_env.split(",") if k.strip()]


@dataclass
class BusConfig:
    max_history: int = _env_int("UC268_BUS_MAX_HISTORY", 10_000)
    default_ttl_ms: int = _env_int("UC268_BUS_DEFAULT_TTL_MS", 30_000)
    enable_metrics: bool = _env_bool("UC268_BUS_ENABLE_METRICS", True)


@dataclass
class AgentConfig:
    agent_name: str = _env_str("UC268_AGENT_NAME", "mustiamente-travel-agent")
    agent_url: str = _env_str("UC268_AGENT_URL", "http://localhost:5268")
    version: str = _env_str("UC268_AGENT_VERSION", "1.0.0")


@dataclass
class AppConfig:
    security: SecurityConfig = field(default_factory=SecurityConfig)
    bus: BusConfig = field(default_factory=BusConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    port: int = _env_int("UC268_PORT", 5268)
    debug: bool = _env_bool("UC268_DEBUG", False)


def get_config() -> AppConfig:
    return AppConfig()


CONFIG = get_config()
