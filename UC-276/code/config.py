"""Configuración centralizada para UC-276 — Recursive Prompting.

Parámetros para las 4 capas de la arquitectura:
1. Calidad (criterios ponderados, umbrales)
2. Refinamiento (estrategias, selección)
3. Estancamiento (plateau, oscilación, degradación)
4. Aplicación (API, agentes demo)
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
class QualityConfig:
    """Criterios de calidad por defecto."""
    default_criteria: dict = field(default_factory=lambda: {
        "clarity": {"weight": 0.25, "min_threshold": 0.5, "target": 0.85},
        "conciseness": {"weight": 0.20, "min_threshold": 0.4, "target": 0.80},
        "completeness": {"weight": 0.25, "min_threshold": 0.5, "target": 0.85},
        "accuracy": {"weight": 0.20, "min_threshold": 0.6, "target": 0.90},
        "coherence": {"weight": 0.10, "min_threshold": 0.5, "target": 0.80},
    })
    target_score: float = _env_float("UC276_TARGET_SCORE", 0.85)
    min_acceptable_score: float = _env_float("UC276_MIN_ACCEPTABLE", 0.60)


@dataclass
class RefinerConfig:
    """Parámetros de refinamiento."""
    max_iterations: int = _env_int("UC276_MAX_ITERATIONS", 5)
    default_temperature: float = _env_float("UC276_TEMPERATURE", 0.5)


@dataclass
class StagnationConfig:
    """Parámetros de detección de estancamiento."""
    min_improvement: float = _env_float("UC276_MIN_IMPROVEMENT", 0.02)
    window_size: int = _env_int("UC276_WINDOW_SIZE", 3)
    max_plateau_iterations: int = _env_int("UC276_MAX_PLATEAU", 2)
    degradation_threshold: float = _env_float("UC276_DEGRADATION_THRESH", 0.05)


@dataclass
class AppConfig:
    """Configuración de la aplicación."""
    port: int = _env_int("UC276_PORT", 5276)
    debug: bool = _env_bool("UC276_DEBUG", False)
    quality: QualityConfig = field(default_factory=QualityConfig)
    refiner: RefinerConfig = field(default_factory=RefinerConfig)
    stagnation: StagnationConfig = field(default_factory=StagnationConfig)


def get_config() -> AppConfig:
    return AppConfig()
