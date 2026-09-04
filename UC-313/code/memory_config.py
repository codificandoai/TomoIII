"""Configuración para la capa de gestión de memoria AGI de UC-296."""
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
class ShortTermMemoryConfig:
    max_notes: int = _env_int("UC296_NOTEPAD_MAX_NOTES", 20)


@dataclass
class StructuredMemoryConfig:
    sqlite_path: str = _env_str("UC296_SQLITE_PATH", "uc296_memory.db")
    pg_uri: str = _env_str("UC296_PG_URI", "")


@dataclass
class VectorMemoryConfig:
    vector_store_path: str = _env_str("UC296_VECTOR_STORE_PATH", "uc296_vectors.json")
    vector_dim: int = _env_int("UC296_VECTOR_DIM", 16)
    use_pgvector: bool = _env_bool("UC296_USE_PGVECTOR", False)
    pg_uri: str = _env_str("UC296_PG_URI", "")
    top_k: int = _env_int("UC296_VECTOR_TOP_K", 3)
    similarity_threshold: float = _env_float("UC296_VECTOR_SIM_THRESHOLD", 0.1)


@dataclass
class SelfModelConfig:
    persistence_path: str = _env_str("UC296_SELF_MODEL_PATH", "uc296_self_model.json")
    sqlite_path: str = _env_str("UC296_SELF_MODEL_SQLITE", "uc296_memory.db")
    max_performance_history: int = _env_int("UC296_PERF_HISTORY", 500)


@dataclass
class SpotlightConfig:
    max_items_in_workspace: int = _env_int("UC296_SPOTLIGHT_MAX_ITEMS", 7)
    novelty_weight: float = _env_float("UC296_SPOTLIGHT_NOVELTY_W", 0.10)
    relevance_weight: float = _env_float("UC296_SPOTLIGHT_RELEVANCE_W", 0.25)
    confidence_weight: float = _env_float("UC296_SPOTLIGHT_CONFIDENCE_W", 0.50)
    recency_weight: float = _env_float("UC296_SPOTLIGHT_RECENCY_W", 0.15)


@dataclass
class GoalConfig:
    allowed_goal_patterns: list[str] = field(default_factory=lambda: [
        "Maximizar retorno ajustado por riesgo",
        "Minimizar drawdown",
        "Maximizar sharpe",
        "Minimizar costos de transacción",
        "Priorizar conservador",
        "Priorizar agresivo",
    ])
    require_approval_for_goal_change: bool = _env_bool("UC296_GOAL_APPROVAL", False)


@dataclass
class MemoryConfig:
    short_term: ShortTermMemoryConfig = field(default_factory=ShortTermMemoryConfig)
    structured: StructuredMemoryConfig = field(default_factory=StructuredMemoryConfig)
    vector: VectorMemoryConfig = field(default_factory=VectorMemoryConfig)
    self_model: SelfModelConfig = field(default_factory=SelfModelConfig)
    spotlight: SpotlightConfig = field(default_factory=SpotlightConfig)
    goals: GoalConfig = field(default_factory=GoalConfig)


@dataclass
class UC296Config:
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    port: int = _env_int("UC296_PORT", 5296)


def get_config() -> UC296Config:
    return UC296Config()
