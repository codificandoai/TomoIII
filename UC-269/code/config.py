"""Configuración centralizada para UC-269 - Protocolo Contract Net."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict


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
class ScoringWeights:
    skill: float = _env_float("UC269_WEIGHT_SKILL", 0.5)
    cost: float = _env_float("UC269_WEIGHT_COST", 0.25)
    latency: float = _env_float("UC269_WEIGHT_LATENCY", 0.15)
    reliability: float = _env_float("UC269_WEIGHT_RELIABILITY", 0.10)

    @property
    def as_dict(self) -> Dict[str, float]:
        return {
            "skill": self.skill,
            "cost": self.cost,
            "latency": self.latency,
            "reliability": self.reliability,
        }


@dataclass
class AppConfig:
    port: int = _env_int("UC269_PORT", 5269)
    debug: bool = _env_bool("UC269_DEBUG", False)
    weights: ScoringWeights = field(default_factory=ScoringWeights)
    enable_prometheus: bool = _env_bool("UC269_ENABLE_PROMETHEUS", True)
    log_level: str = _env_str("UC269_LOG_LEVEL", "INFO")


def get_config() -> AppConfig:
    return AppConfig()


CONFIG = get_config()
