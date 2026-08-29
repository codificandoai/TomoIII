"""Energy Marketplace P2P para UC-274.

Orquesta el ecosistema completo Web3:
- Registra agentes (wallet + DID + ENS name).
- Despliega contratos (energía, escrow, reputación, settlement).
- Gestiona ofertas, trades, entregas y liquidación.
- Auditoría transparente (explorer de bloques y transacciones).
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from blockchain import Blockchain, BlockchainState, Transaction
from config import AppConfig, get_config
from consensus import BFTConsensusEngine
from contracts import (
    EnergyTradeContract,
    EscrowContract,
    ReputationContract,
    SettlementContract,
    deploy_contract,
)
from models import TransactionType
from wallet import DID, DIDRegistry, Wallet


class AgentAccount:
    """Cuenta de agente en el marketplace."""

    def __init__(self, wallet: Wallet, did: DID, name: str = "") -> None:
        self.wallet = wallet
        self.did = did
        self.name = name


class EnergyMarketplace:
    """Marketplace descentralizado de energía P2P con blockchain BFT."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or get_config()
        self.did_registry = DIDRegistry()

        # Crea validadores
        self._validator_wallets: List[Wallet] = [Wallet() for _ in range(4)]
        self.blockchain = Blockchain(self._validator_wallets, self.did_registry)

        # Consenso BFT
        self.consensus = BFTConsensusEngine(self._validator_wallets)

        # Agentes registrados
        self.agents: Dict[str, AgentAccount] = {}

        # Contratos desplegados
        self.energy_contract: Optional[EnergyTradeContract] = None
        self.escrow_contract: Optional[EscrowContract] = None
        self.reputation_contract: Optional[ReputationContract] = None
        self.settlement_contract: Optional[SettlementContract] = None

        # Mint initial balance para validadores
        for v in self._validator_wallets:
            self.blockchain.mint(v.address, self.config.blockchain.initial_balance_wei)

        # Despliega contratos base
        self._deploy_base_contracts()

    def _deploy_base_contracts(self) -> None:
        deployer = self._validator_wallets[0]
        state = self.blockchain.state

        self.energy_contract = EnergyTradeContract(
            address="0xenergy_contract",
            deployer=deployer.address,
            state=state,
            init_params={"fee_bps": self.config.contracts.energy_fee_bps,
                         "oracles": [deployer.address]},
        )
        self.blockchain.contracts["0xenergy_contract"] = self.energy_contract

        self.escrow_contract = EscrowContract(
            address="0xescrow_contract",
            deployer=deployer.address,
            state=state,
            init_params={"timeout_seconds": self.config.contracts.escrow_timeout_seconds},
        )
        self.blockchain.contracts["0xescrow_contract"] = self.escrow_contract

        self.reputation_contract = ReputationContract(
            address="0xreputation_contract",
            deployer=deployer.address,
            state=state,
            init_params={},
        )
        self.blockchain.contracts["0xreputation_contract"] = self.reputation_contract

        self.settlement_contract = SettlementContract(
            address="0xsettlement_contract",
            deployer=deployer.address,
            state=state,
            init_params={"fee_bps": 30},
        )
        self.blockchain.contracts["0xsettlement_contract"] = self.settlement_contract

    # ================================================================
    # Agent Management
    # ================================================================

    def register_agent(self, name: str, initial_balance: int = 0,
                       metadata: dict | None = None) -> dict:
        """Registra un nuevo agente con wallet, DID y nombre ENS-like."""
        if name in self.agents:
            raise ValueError(f"Agent {name} already registered")

        wallet = Wallet()
        did = DID.create(wallet, metadata=metadata or {"role": "prosumer"})
        self.did_registry.register(did)
        self.did_registry.register_name(name, wallet.address)

        if initial_balance > 0:
            self.blockchain.mint(wallet.address, initial_balance)

        account = AgentAccount(wallet=wallet, did=did, name=name)
        self.agents[name] = account

        return {
            "name": name,
            "address": wallet.address,
            "did": did.did,
            "public_key_b64": wallet.public_key_b64(),
            "balance_wei": self.blockchain.state.balances[wallet.address],
        }

    def get_agent(self, name: str) -> Optional[dict]:
        account = self.agents.get(name)
        if not account:
            return None
        addr = account.wallet.address
        return {
            "name": name,
            "address": addr,
            "did": account.did.did,
            "balance_wei": self.blockchain.state.balances[addr],
            "nonce": self.blockchain.state.nonces[addr],
            "reputation": round(self.blockchain.state.reputation[addr], 4),
        }

    def list_agents(self) -> List[dict]:
        return [self.get_agent(n) for n in self.agents]

    # ================================================================
    # Energy Trading
    # ================================================================

    def create_energy_offer(self, agent_name: str, side: str = "sell",
                            quantity_kwh: float = 10.0,
                            price_per_kwh_wei: int = 1000,
                            energy_source: str = "solar") -> dict:
        account = self.agents.get(agent_name)
        if not account:
            return {"error": "agent_not_found"}

        result = self.energy_contract.method_create_offer(
            creator=account.wallet.address,
            side=side,
            quantity_kwh=quantity_kwh,
            price_per_kwh_wei=price_per_kwh_wei,
            energy_source=energy_source,
        )
        return result

    def match_trade(self, buyer_name: str, offer_id: str,
                    quantity_kwh: float) -> dict:
        buyer = self.agents.get(buyer_name)
        if not buyer:
            return {"error": "buyer_not_found"}

        result = self.energy_contract.method_match_and_trade(
            buyer=buyer.wallet.address,
            offer_id=offer_id,
            quantity_kwh=quantity_kwh,
        )
        return result

    def confirm_delivery(self, trade_id: str) -> dict:
        """Oracle (validador 0) confirma entrega de energía."""
        oracle = self._validator_wallets[0]
        result = self.energy_contract.method_confirm_delivery(
            caller=oracle.address,
            trade_id=trade_id,
        )
        return result

    def get_offers(self, status: str = "open") -> List[dict]:
        return self.energy_contract.get_offers(status)

    def get_trades(self) -> List[dict]:
        return self.energy_contract.get_trades()

    # ================================================================
    # Escrow
    # ================================================================

    def create_escrow(self, depositor_name: str, beneficiary_name: str,
                      amount_wei: int, condition: str = "") -> dict:
        dep = self.agents.get(depositor_name)
        ben = self.agents.get(beneficiary_name)
        if not dep:
            return {"error": "depositor_not_found"}
        if not ben:
            return {"error": "beneficiary_not_found"}

        return self.escrow_contract.method_deposit(
            depositor=dep.wallet.address,
            beneficiary=ben.wallet.address,
            amount_wei=amount_wei,
            condition=condition,
        )

    def release_escrow(self, caller_name: str, escrow_id: str) -> dict:
        caller = self.agents.get(caller_name)
        if not caller:
            return {"error": "caller_not_found"}
        return self.escrow_contract.method_release(
            caller=caller.wallet.address, escrow_id=escrow_id
        )

    # ================================================================
    # Reputation
    # ================================================================

    def record_trade_reputation(self, trader_name: str, success: bool = True) -> dict:
        trader = self.agents.get(trader_name)
        if not trader:
            return {"error": "trader_not_found"}
        deployer = self._validator_wallets[0]
        return self.reputation_contract.method_record_trade(
            caller=deployer.address,
            trader=trader.wallet.address,
            success=success,
        )

    def endorse_agent(self, endorser_name: str, target_name: str,
                      score: float = 1.0) -> dict:
        endorser = self.agents.get(endorser_name)
        target = self.agents.get(target_name)
        if not endorser:
            return {"error": "endorser_not_found"}
        if not target:
            return {"error": "target_not_found"}
        return self.reputation_contract.method_endorse(
            endorser=endorser.wallet.address,
            target=target.wallet.address,
            score=score,
        )

    def get_reputation(self, agent_name: str) -> dict:
        agent = self.agents.get(agent_name)
        if not agent:
            return {"error": "agent_not_found"}
        return self.reputation_contract.get_reputation(agent.wallet.address)

    # ================================================================
    # Blockchain Operations
    # ================================================================

    def mine_block(self, validator_index: int = 0) -> Optional[dict]:
        """Mina un bloque con consenso BFT."""
        proposer = self._validator_wallets[validator_index % len(self._validator_wallets)]
        block = self.blockchain.propose_and_commit_block(proposer, self.consensus)
        if block:
            return block.to_dict()
        return None

    def get_block(self, number: int) -> Optional[dict]:
        block = self.blockchain.get_block(number)
        return block.to_dict() if block else None

    def verify_chain(self) -> dict:
        valid, broken_at = self.blockchain.verify_chain()
        return {"valid": valid, "broken_at_index": broken_at, "block_height": self.blockchain.block_height}

    def get_chain_status(self) -> dict:
        total_txs = sum(len(b.transactions) for b in self.blockchain.blocks)
        return {
            "block_height": self.blockchain.block_height,
            "total_transactions": total_txs,
            "validator_count": len(self._validator_wallets),
            "validators": [v.address for v in self._validator_wallets],
            "chain_valid": self.blockchain.verify_chain()[0],
            "state_root": self.blockchain.state.compute_state_root(),
            "pending_txs": len(self.blockchain.pending_txs),
            "contracts_deployed": len(self.blockchain.contracts),
            "agents_registered": len(self.agents),
            "consensus_rounds": self.consensus.consensus_count,
        }

    def get_marketplace_status(self) -> dict:
        trades = self.energy_contract.get_trades() if self.energy_contract else []
        offers = self.energy_contract.get_offers("open") if self.energy_contract else []
        total_kwh = sum(t["quantity_kwh"] for t in trades)
        total_vol = sum(t["total_wei"] for t in trades)
        return {
            "total_agents": len(self.agents),
            "active_offers": len(offers),
            "completed_trades": len([t for t in trades if t["status"] == "delivered"]),
            "pending_trades": len([t for t in trades if t["status"] == "pending_delivery"]),
            "total_energy_kwh": round(total_kwh, 2),
            "total_volume_wei": total_vol,
            "validators": [v.address[:16] + "..." for v in self._validator_wallets],
        }
