"""Configuración centralizada para UC-273 — Seguridad Multi-Agente.

Integra parámetros para las 7 capas de seguridad + guardrails de atlas-demo.
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
class CryptoConfig:
    """Configuración de autenticación criptográfica Ed25519."""
    nonce_window_seconds: float = _env_float("UC273_NONCE_WINDOW", 300.0)
    max_nonce_cache: int = _env_int("UC273_MAX_NONCE_CACHE", 100_000)


@dataclass
class TrustConfig:
    """Configuración del trust scoring bayesiano."""
    quarantine_threshold: float = _env_float("UC273_QUARANTINE_THRESHOLD", 0.3)
    trusted_threshold: float = _env_float("UC273_TRUSTED_THRESHOLD", 0.7)
    decay_rate: float = _env_float("UC273_TRUST_DECAY_RATE", 0.001)
    failure_weight_multiplier: float = _env_float("UC273_FAILURE_WEIGHT", 2.0)


@dataclass
class RateLimitConfig:
    """Configuración del rate limiter por agente."""
    rate_per_second: float = _env_float("UC273_RATE_PER_SEC", 10.0)
    burst_capacity: int = _env_int("UC273_BURST_CAPACITY", 50)
    max_payload_bytes: int = _env_int("UC273_MAX_PAYLOAD_BYTES", 65536)
    max_payload_fields: int = _env_int("UC273_MAX_PAYLOAD_FIELDS", 100)


@dataclass
class AnomalyConfig:
    """Configuración de detección de anomalías."""
    spoofing_window_size: int = _env_int("UC273_SPOOF_WINDOW", 1000)
    cancel_ratio_threshold: float = _env_float("UC273_CANCEL_RATIO", 0.85)
    fast_cancel_ms: float = _env_float("UC273_FAST_CANCEL_MS", 500.0)
    z_score_threshold: float = _env_float("UC273_Z_SCORE", 3.5)
    collusion_correlation: float = _env_float("UC273_COLLUSION_CORR", 0.85)
    collusion_min_observations: int = _env_int("UC273_COLLUSION_MIN_OBS", 50)


@dataclass
class GuardrailsConfig:
    """Guardrails integrados de atlas-demo."""
    enable_injection_scan: bool = _env_bool("UC273_INJECTION_SCAN", True)
    enable_dlp_redaction: bool = _env_bool("UC273_DLP_REDACTION", True)
    enable_bola_guard: bool = _env_bool("UC273_BOLA_GUARD", True)
    enable_egress_policy: bool = _env_bool("UC273_EGRESS_POLICY", True)
    enable_agent_identity: bool = _env_bool("UC273_AGENT_IDENTITY", True)
    allowed_egress_hosts: tuple[str, ...] = field(default_factory=lambda: tuple(
        h.strip() for h in _env("UC273_ALLOWED_HOSTS", "finance.internal,api.atlas.demo").split(",") if h.strip()
    ))
    agent_jwt_secret: str = field(default_factory=lambda: _env("UC273_JWT_SECRET", "atlas-agent-authority-secret-key-2026"))
    trusted_identity: str = field(default_factory=lambda: _env("UC273_TRUSTED_IDENTITY", "spiffe://atlas/planner"))


@dataclass
class AppConfig:
    port: int = _env_int("UC273_PORT", 5273)
    debug: bool = _env_bool("UC273_DEBUG", False)
    crypto: CryptoConfig = field(default_factory=CryptoConfig)
    trust: TrustConfig = field(default_factory=TrustConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    anomaly: AnomalyConfig = field(default_factory=AnomalyConfig)
    guardrails: GuardrailsConfig = field(default_factory=GuardrailsConfig)


def get_config() -> AppConfig:
    return AppConfig()
