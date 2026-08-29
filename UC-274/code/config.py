"""Configuración centralizada para UC-274 — Web3 Multi-Agent Blockchain.

Parámetros para las 4 capas de la arquitectura:
1. Identidad Web3 (Wallets Ed25519, DIDs)
2. Consenso BFT (PoA, PBFT-lite)
3. Smart Contracts (Energy, Escrow, Reputation, Settlement)
4. Aplicación (Marketplace, API)
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
class BlockchainConfig:
    """Parámetros de la blockchain PoA."""
    max_txs_per_block: int = _env_int("UC274_MAX_TXS_BLOCK", 100)
    block_time_seconds: float = _env_float("UC274_BLOCK_TIME", 2.0)
    initial_balance_wei: int = _env_int("UC274_INITIAL_BALANCE", 10_000_000)
    gas_limit_default: int = _env_int("UC274_GAS_LIMIT", 100_000)


@dataclass
class ConsensusConfig:
    """Parámetros del consenso BFT."""
    min_validators: int = _env_int("UC274_MIN_VALIDATORS", 4)
    byzantine_tolerance_fraction: float = 1 / 3  # f < n/3


@dataclass
class ContractConfig:
    """Parámetros de smart contracts."""
    energy_fee_bps: int = _env_int("UC274_ENERGY_FEE_BPS", 50)  # 0.5%
    escrow_timeout_seconds: float = _env_float("UC274_ESCROW_TIMEOUT", 86400.0)
    reputation_initial: float = _env_float("UC274_REP_INITIAL", 0.5)
    reputation_decay_rate: float = _env_float("UC274_REP_DECAY", 0.001)


@dataclass
class AppConfig:
    """Configuración de la aplicación."""
    port: int = _env_int("UC274_PORT", 5274)
    debug: bool = _env_bool("UC274_DEBUG", False)
    blockchain: BlockchainConfig = field(default_factory=BlockchainConfig)
    consensus: ConsensusConfig = field(default_factory=ConsensusConfig)
    contracts: ContractConfig = field(default_factory=ContractConfig)


def get_config() -> AppConfig:
    return AppConfig()
