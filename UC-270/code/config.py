"""Configuración centralizada para UC-270 - Resolución de Conflictos entre Agentes."""
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
class ResolutionWeights:
    """Pesos para la función de scoring de autoridad superior."""
    priority: float = _env_float("UC270_WEIGHT_PRIORITY", 0.40)
    need: float = _env_float("UC270_WEIGHT_NEED", 0.30)
    willingness: float = _env_float("UC270_WEIGHT_WILLINGNESS", 0.15)
    reputation: float = _env_float("UC270_WEIGHT_REPUTATION", 0.15)


@dataclass
class NegotiationConfig:
    max_rounds: int = _env_int("UC270_MAX_NEGOTIATION_ROUNDS", 5)
    agreement_base_prob: float = _env_float("UC270_AGREEMENT_BASE_PROB", 0.35)
    concession_rate: float = _env_float("UC270_CONCESSION_RATE", 0.10)


@dataclass
class AppConfig:
    port: int = _env_int("UC270_PORT", 5270)
    debug: bool = _env_bool("UC270_DEBUG", False)
    weights: ResolutionWeights = field(default_factory=ResolutionWeights)
    negotiation: NegotiationConfig = field(default_factory=NegotiationConfig)
    seed: int = _env_int("UC270_SEED", 42)


def get_config() -> AppConfig:
    return AppConfig()
