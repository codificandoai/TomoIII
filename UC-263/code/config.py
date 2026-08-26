"""Configuración centralizada para UC-263 - Q-Learning vectorial para recomendaciones turísticas."""
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
class RLLearningConfig:
    """Hiperparámetros del Q-Learning vectorial."""

    embedding_dim: int = _env_int("UC263_EMBEDDING_DIM", 16)
    alpha: float = _env_float("UC263_ALPHA", 0.2)
    gamma: float = _env_float("UC263_GAMMA", 0.9)
    epsilon: float = _env_float("UC263_EPSILON", 0.3)
    episodes: int = _env_int("UC263_EPISODES", 50)
    k_neighbors: int = _env_int("UC263_K_NEIGHBORS", 5)
    decay: float = _env_float("UC263_EPSILON_DECAY", 0.98)


@dataclass
class MemoryConfig:
    path: str = _env_str("UC263_MEMORY_PATH", "")


@dataclass
class AgentConfig:
    actions: list = field(
        default_factory=lambda: [
            "Museo",
            "Aventura",
            "Gastronomía",
            "Descanso",
            "Playa",
            "Naturaleza",
            "Compras",
            "Evento cultural",
        ]
    )
    seed: int = _env_int("UC263_SEED", 42)


@dataclass
class AppConfig:
    rl: RLLearningConfig = field(default_factory=RLLearningConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    port: int = _env_int("UC263_PORT", 5263)


def get_config() -> AppConfig:
    return AppConfig()


CONFIG = get_config()
