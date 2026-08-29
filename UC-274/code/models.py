"""Modelos Pydantic para UC-274 — Web3 Multi-Agent Blockchain.

Cubre las 4 capas de la arquitectura:
1. Identidad Web3 (DID, Wallet metadata)
2. Blockchain (Transaction, Block, State)
3. Smart Contracts (Energy, Escrow, Reputation, Settlement)
4. Aplicación (Marketplace, API responses)
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ============================================================
# Enums
# ============================================================

class TransactionType(str, Enum):
    transfer = "transfer"
    energy_trade = "energy_trade"
    escrow_deposit = "escrow_deposit"
    escrow_release = "escrow_release"
    escrow_refund = "escrow_refund"
    reputation_update = "reputation_update"
    contract_deploy = "contract_deploy"
    contract_call = "contract_call"
    validator_vote = "validator_vote"


class BFTPhase(str, Enum):
    pre_prepare = "pre_prepare"
    prepare = "prepare"
    commit = "commit"


class OfferSide(str, Enum):
    buy = "buy"
    sell = "sell"


class OfferStatus(str, Enum):
    open = "open"
    filled = "filled"
    cancelled = "cancelled"


class TradeStatus(str, Enum):
    pending_delivery = "pending_delivery"
    delivered = "delivered"
    settled = "settled"
    disputed = "disputed"


class EscrowStatus(str, Enum):
    locked = "locked"
    released = "released"
    refunded = "refunded"
    expired = "expired"


# ============================================================
# Identity / DID
# ============================================================

class DIDDocument(BaseModel):
    """DID Document según W3C DID Core v1."""
    context: str = Field(default="https://www.w3.org/ns/did/v1", alias="@context")
    id: str
    controller: str
    verification_method: List[Dict[str, str]] = Field(default_factory=list)
    authentication: List[str] = Field(default_factory=list)
    created: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True


class WalletInfo(BaseModel):
    """Información pública de un wallet."""
    address: str
    public_key_b64: str
    did: str = ""
    balance_wei: int = 0
    nonce: int = 0
    reputation: float = 0.5


# ============================================================
# Blockchain
# ============================================================

class TransactionModel(BaseModel):
    """Transacción en la blockchain."""
    tx_id: str
    nonce: int
    from_address: str
    to_address: Optional[str] = None
    tx_type: str
    value_wei: int = 0
    data: Dict[str, Any] = Field(default_factory=dict)
    gas_limit: int = 100_000
    timestamp: float = 0.0


class BlockHeaderModel(BaseModel):
    """Header de un bloque."""
    block_number: int
    parent_hash: str
    timestamp: float
    validator_address: str
    transactions_root: str
    state_root: str
    consensus_proof: Dict[str, Any] = Field(default_factory=dict)


class BlockModel(BaseModel):
    """Bloque de la blockchain."""
    header: BlockHeaderModel
    transactions: List[TransactionModel] = Field(default_factory=list)
    block_hash: str
    tx_count: int = 0


class ChainStatus(BaseModel):
    """Estado de la cadena."""
    block_height: int = 0
    total_transactions: int = 0
    validator_count: int = 0
    chain_valid: bool = True
    state_root: str = ""
    pending_txs: int = 0


# ============================================================
# Smart Contracts
# ============================================================

class EnergyOffer(BaseModel):
    """Oferta de compra/venta de energía."""
    offer_id: str
    creator: str
    side: str
    quantity_kwh: float
    remaining_kwh: float
    price_per_kwh_wei: int
    energy_source: str = "solar"
    delivery_window: List[float] = Field(default_factory=list)
    status: str = "open"
    created_at: float = 0.0


class EnergyTrade(BaseModel):
    """Trade de energía P2P."""
    trade_id: str
    buyer: str
    seller: str
    quantity_kwh: float
    price_per_kwh_wei: int
    total_wei: int
    energy_source: str = "solar"
    status: str = "pending_delivery"
    created_at: float = 0.0


class EscrowInfo(BaseModel):
    """Información de un escrow."""
    escrow_id: str
    depositor: str
    beneficiary: str
    amount_wei: int
    status: str = "locked"
    condition: str = ""
    created_at: float = 0.0
    timeout_at: float = 0.0


class ReputationRecord(BaseModel):
    """Registro de reputación on-chain."""
    address: str
    reputation: float = 0.5
    total_trades: int = 0
    successful_trades: int = 0
    disputes: int = 0


# ============================================================
# API Responses
# ============================================================

class MarketplaceStatus(BaseModel):
    """Estado del marketplace."""
    total_agents: int = 0
    active_offers: int = 0
    completed_trades: int = 0
    total_energy_kwh: float = 0.0
    total_volume_wei: int = 0
    validators: List[str] = Field(default_factory=list)
