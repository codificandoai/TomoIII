"""Configuración centralizada para UC-275 — Autorreflexión de Agentes.

Parámetros para las 5 capas de la arquitectura:
1. Evaluación (criterios ponderados, umbrales)
2. Crítica (heurísticas de causa raíz)
3. Refinamiento (límites de iteración, mejora mínima)
4. Memoria episódica (capacidad, similitud)
5. Aplicación (API, agentes demo)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
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
class EvaluationConfig:
    """Criterios y umbrales de evaluación."""
    default_weights: dict = field(default_factory=lambda: {
        "correctness": 0.40,
        "completeness": 0.25,
        "clarity": 0.20,
        "efficiency": 0.15,
    })
    convergence_threshold: float = _env_float("UC275_CONVERGENCE", 0.80)
    needs_reflection_score: float = _env_float("UC275_REFLECT_SCORE", 0.70)
    needs_reflection_severity: float = _env_float("UC275_REFLECT_SEVERITY", 0.50)


@dataclass
class CriticConfig:
    """Parámetros del auto-crítico."""
    heuristic_min_confidence: float = _env_float("UC275_HEURISTIC_MIN_CONF", 0.30)
    fallback_severity_threshold: float = _env_float("UC275_FALLBACK_SEVERITY", 0.70)


@dataclass
class RefinerConfig:
    """Parámetros de refinamiento."""
    max_iterations: int = _env_int("UC275_MAX_ITERATIONS", 3)
    min_improvement_threshold: float = _env_float("UC275_MIN_IMPROVEMENT", 0.10)
    max_refinement_steps: int = _env_int("UC275_MAX_REFINE_STEPS", 3)


@dataclass
class MemoryConfig:
    """Parámetros de la memoria episódica."""
    max_episodes: int = _env_int("UC275_MAX_EPISODES", 1000)
    similarity_threshold: float = _env_float("UC275_SIMILARITY_THRESH", 0.70)
    max_success_patterns: int = _env_int("UC275_MAX_SUCCESS_PATTERNS", 500)
    max_failure_patterns: int = _env_int("UC275_MAX_FAILURE_PATTERNS", 500)


@dataclass
class AppConfig:
    """Configuración de la aplicación."""
    port: int = _env_int("UC275_PORT", 5275)
    debug: bool = _env_bool("UC275_DEBUG", False)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    critic: CriticConfig = field(default_factory=CriticConfig)
    refiner: RefinerConfig = field(default_factory=RefinerConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)


def get_config() -> AppConfig:
    return AppConfig()
