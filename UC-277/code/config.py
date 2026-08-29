"""Configuracion centralizada para UC-277 — Memoria Multi-Turno a Largo Plazo.

5 capas de memoria + persistencia SQLite + embeddings.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


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
    return val.strip().lower() in ("1", "true", "yes")


@dataclass
class WorkingMemoryConfig:
    capacity: int = _env_int("UC277_WM_CAPACITY", 7)


@dataclass
class EpisodicConfig:
    max_episodes: int = _env_int("UC277_MAX_EPISODES", 10000)
    min_similarity: float = _env_float("UC277_MIN_SIMILARITY", 0.3)
    decay_rate: float = _env_float("UC277_DECAY_RATE", 0.01)


@dataclass
class SemanticConfig:
    similarity_threshold: float = _env_float("UC277_SEMANTIC_THRESH", 0.85)


@dataclass
class ProceduralConfig:
    ema_alpha: float = _env_float("UC277_EMA_ALPHA", 0.3)


@dataclass
class GoalConfig:
    max_active_goals: int = _env_int("UC277_MAX_GOALS", 20)


@dataclass
class EmbeddingConfig:
    dimension: int = _env_int("UC277_EMBED_DIM", 64)


@dataclass
class AppConfig:
    port: int = _env_int("UC277_PORT", 5277)
    debug: bool = _env_bool("UC277_DEBUG", False)
    db_path: str = os.getenv("UC277_DB_PATH", ":memory:")
    working: WorkingMemoryConfig = field(default_factory=WorkingMemoryConfig)
    episodic: EpisodicConfig = field(default_factory=EpisodicConfig)
    semantic: SemanticConfig = field(default_factory=SemanticConfig)
    procedural: ProceduralConfig = field(default_factory=ProceduralConfig)
    goal: GoalConfig = field(default_factory=GoalConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)


def get_config() -> AppConfig:
    return AppConfig()
