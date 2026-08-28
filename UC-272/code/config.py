"""Configuración centralizada para UC-272 — Negociación y Compartición de Conocimiento."""
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
class NegotiationConfig:
    max_rounds: int = _env_int("UC272_MAX_ROUNDS", 10)
    discount_factor: float = _env_float("UC272_DISCOUNT_FACTOR", 0.95)
    concession_exponent: float = _env_float("UC272_CONCESSION_EXP", 2.0)
    vickrey_reserve_price: float = _env_float("UC272_VICKREY_RESERVE", 0.0)


@dataclass
class BlackboardConfig:
    default_ttl_seconds: int = _env_int("UC272_BB_TTL", 3600)
    min_confidence: float = _env_float("UC272_BB_MIN_CONFIDENCE", 0.5)


@dataclass
class GossipConfig:
    max_hops: int = _env_int("UC272_GOSSIP_MAX_HOPS", 3)
    decay_factor: float = _env_float("UC272_GOSSIP_DECAY", 0.95)


@dataclass
class AppConfig:
    port: int = _env_int("UC272_PORT", 5272)
    debug: bool = _env_bool("UC272_DEBUG", False)
    negotiation: NegotiationConfig = field(default_factory=NegotiationConfig)
    blackboard: BlackboardConfig = field(default_factory=BlackboardConfig)
    gossip: GossipConfig = field(default_factory=GossipConfig)


def get_config() -> AppConfig:
    return AppConfig()
