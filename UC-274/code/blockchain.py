"""Blockchain con Proof of Authority para UC-274.

Implementa:
- Transaction: transacción firmada Ed25519 con nonce, tipo, payload.
- BlockHeader + Block: bloques con Merkle root de transacciones.
- BlockchainState: estado global (balances, nonces, contratos, reputación).
- Blockchain: cadena de bloques con PoA, mint, bloque génesis, verificación.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from wallet import Wallet, DID, DIDRegistry
from models import TransactionType


class Transaction(BaseModel):
    """Transacción firmada."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tx_id: str = Field(default_factory=lambda: uuid4().hex)
    nonce: int
    from_address: str
    to_address: Optional[str] = None
    tx_type: TransactionType
    value_wei: int = 0
    data: Dict[str, Any] = Field(default_factory=dict)
    gas_limit: int = 100_000
    timestamp: float = Field(default_factory=time.time)
    signature: bytes = b""

    def signing_payload(self) -> bytes:
        payload = {
            "tx_id": self.tx_id,
            "nonce": self.nonce,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "tx_type": self.tx_type.value,
            "value_wei": self.value_wei,
            "data": self.data,
            "gas_limit": self.gas_limit,
            "timestamp": self.timestamp,
        }
        return json.dumps(payload, sort_keys=True).encode("utf-8")

    def sign_with(self, wallet: Wallet) -> "Transaction":
        sig = wallet.sign(self.signing_payload())
        return self.model_copy(update={"signature": sig})

    def verify_signature(self, public_key_b64: str) -> bool:
        try:
            import base64
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            pub_bytes = base64.b64decode(public_key_b64)
            pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
            pub_key.verify(self.signature, self.signing_payload())
            return True
        except Exception:
            return False

    def to_dict(self) -> dict:
        return {
            "tx_id": self.tx_id,
            "nonce": self.nonce,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "tx_type": self.tx_type.value,
            "value_wei": self.value_wei,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class BlockHeader(BaseModel):
    model_config = ConfigDict(frozen=True)

    block_number: int
    parent_hash: str
    timestamp: float
    validator_address: str
    transactions_root: str
    state_root: str
    consensus_proof: Dict[str, Any] = Field(default_factory=dict)

    def compute_hash(self) -> str:
        content = (
            f"{self.block_number}|{self.parent_hash}|{self.timestamp}|"
            f"{self.validator_address}|{self.transactions_root}|{self.state_root}"
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


class Block(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    header: BlockHeader
    transactions: List[Transaction] = Field(default_factory=list)
    block_hash: str = ""
    validator_signature: bytes = b""

    @classmethod
    def create(cls, block_number: int, parent_hash: str,
               transactions: List[Transaction],
               validator_address: str, state_root: str,
               consensus_proof: dict | None = None) -> Block:
        header = BlockHeader(
            block_number=block_number,
            parent_hash=parent_hash,
            timestamp=time.time(),
            validator_address=validator_address,
            transactions_root=cls._compute_tx_root(transactions),
            state_root=state_root,
            consensus_proof=consensus_proof or {},
        )
        block_hash = header.compute_hash()
        return cls(header=header, transactions=transactions, block_hash=block_hash)

    @staticmethod
    def _compute_tx_root(transactions: List[Transaction]) -> str:
        """Merkle root simplificado de transacciones."""
        if not transactions:
            return hashlib.sha256(b"empty").hexdigest()
        hashes = [hashlib.sha256(tx.signing_payload()).hexdigest() for tx in transactions]
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])
            next_level = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i + 1]
                next_level.append(hashlib.sha256(combined.encode("utf-8")).hexdigest())
            hashes = next_level
        return hashes[0]

    def sign_with(self, wallet: Wallet) -> "Block":
        sig = wallet.sign(self.block_hash.encode("utf-8"))
        return self.model_copy(update={"validator_signature": sig})

    def to_dict(self) -> dict:
        return {
            "block_number": self.header.block_number,
            "block_hash": self.block_hash,
            "parent_hash": self.header.parent_hash,
            "timestamp": self.header.timestamp,
            "validator": self.header.validator_address,
            "tx_count": len(self.transactions),
            "state_root": self.header.state_root,
            "consensus": self.header.consensus_proof,
        }


class BlockchainState:
    """Estado global del sistema (cuentas + contratos + reputación)."""

    def __init__(self) -> None:
        self.balances: Dict[str, int] = defaultdict(int)
        self.nonces: Dict[str, int] = defaultdict(int)
        self.contracts: Dict[str, dict] = {}
        self.reputation: Dict[str, float] = defaultdict(lambda: 0.5)

    def apply_transaction(self, tx: Transaction) -> bool:
        if tx.nonce != self.nonces[tx.from_address]:
            return False
        if tx.tx_type == TransactionType.transfer:
            if self.balances[tx.from_address] < tx.value_wei:
                return False
            self.balances[tx.from_address] -= tx.value_wei
            if tx.to_address:
                self.balances[tx.to_address] += tx.value_wei
        self.nonces[tx.from_address] += 1
        return True

    def compute_state_root(self) -> str:
        state = {
            "balances": dict(sorted(self.balances.items())),
            "nonces": dict(sorted(self.nonces.items())),
            "contracts": {k: str(v) for k, v in sorted(self.contracts.items())},
            "reputation": dict(sorted(self.reputation.items())),
        }
        return hashlib.sha256(json.dumps(state, sort_keys=True).encode("utf-8")).hexdigest()

    def snapshot(self) -> dict:
        return {
            "balances": dict(self.balances),
            "nonces": dict(self.nonces),
            "contracts": dict(self.contracts),
            "reputation": dict(self.reputation),
        }

    def copy(self) -> "BlockchainState":
        new = BlockchainState()
        new.balances = defaultdict(int, self.balances)
        new.nonces = defaultdict(int, self.nonces)
        new.contracts = {k: dict(v) for k, v in self.contracts.items()}
        new.reputation = defaultdict(lambda: 0.5, self.reputation)
        return new


class Blockchain:
    """Blockchain con Proof of Authority y consenso BFT."""

    def __init__(self, validators: List[Wallet], did_registry: DIDRegistry | None = None) -> None:
        self.validators = validators
        self.validator_addresses = {w.address for w in validators}
        self.blocks: List[Block] = []
        self.pending_txs: deque[Transaction] = deque()
        self.state = BlockchainState()
        self.contracts: Dict[str, Any] = {}
        self.did_registry = did_registry or DIDRegistry()
        self._create_genesis_block()

    def _create_genesis_block(self) -> None:
        genesis = Block.create(
            block_number=0,
            parent_hash="0" * 64,
            transactions=[],
            validator_address=self.validators[0].address,
            state_root=self.state.compute_state_root(),
            consensus_proof={"type": "genesis"},
        )
        self.blocks.append(genesis)

    @property
    def latest_block(self) -> Block:
        return self.blocks[-1]

    @property
    def block_height(self) -> int:
        return len(self.blocks) - 1

    def submit_transaction(self, tx: Transaction) -> str:
        self.pending_txs.append(tx)
        return tx.tx_id

    def mint(self, address: str, amount_wei: int) -> None:
        self.state.balances[address] += amount_wei

    def propose_and_commit_block(self, proposer: Wallet,
                                 consensus_engine=None) -> Optional[Block]:
        """Propone bloque y ejecuta consenso BFT."""
        if proposer.address not in self.validator_addresses:
            raise ValueError(f"{proposer.address} is not a validator")

        txs: List[Transaction] = []
        while self.pending_txs and len(txs) < 100:
            txs.append(self.pending_txs.popleft())

        if not txs:
            return None

        valid_txs: List[Transaction] = []
        state_copy = self.state.copy()
        for tx in txs:
            if self._validate_tx(tx, state_copy):
                state_copy.apply_transaction(tx)
                valid_txs.append(tx)

        if not valid_txs:
            return None

        new_block = Block.create(
            block_number=self.block_height + 1,
            parent_hash=self.latest_block.block_hash,
            transactions=valid_txs,
            validator_address=proposer.address,
            state_root=state_copy.compute_state_root(),
        )

        # Consenso BFT
        consensus_proof: Optional[dict] = None
        if consensus_engine:
            consensus_proof = consensus_engine.run_full_protocol(new_block, proposer)
        else:
            consensus_proof = self._simple_consensus(new_block, proposer)

        if consensus_proof is None:
            for tx in valid_txs:
                self.pending_txs.appendleft(tx)
            return None

        self.state = state_copy

        # Ejecuta contratos
        for tx in valid_txs:
            self._execute_contract_tx(tx)

        new_block = new_block.model_copy(
            update={"header": new_block.header.model_copy(
                update={"consensus_proof": consensus_proof}
            )}
        )
        new_block = new_block.sign_with(proposer)
        self.blocks.append(new_block)
        return new_block

    def _validate_tx(self, tx: Transaction, state: BlockchainState) -> bool:
        did = self.did_registry.resolve_by_address(tx.from_address)
        if did is not None:
            if not tx.verify_signature(did.public_key_b64):
                return False
        if tx.nonce != state.nonces[tx.from_address]:
            return False
        if tx.tx_type == TransactionType.transfer:
            if state.balances[tx.from_address] < tx.value_wei:
                return False
        return True

    def _execute_contract_tx(self, tx: Transaction) -> None:
        if tx.tx_type == TransactionType.contract_call:
            contract = self.contracts.get(tx.to_address)
            if contract:
                contract.execute(tx)

    def _simple_consensus(self, block: Block, proposer: Wallet) -> Optional[dict]:
        """Consenso simplificado: todos los validadores votan."""
        n = len(self.validators)
        f = (n - 1) // 3
        required = 2 * f + 1

        votes = {}
        for v in self.validators:
            if block.block_hash == block.header.compute_hash():
                sig = v.sign(block.block_hash.encode("utf-8"))
                votes[v.address] = sig.hex()

        if len(votes) >= required:
            return {
                "type": "bft_commit",
                "block_hash": block.block_hash,
                "quorum_size": len(votes),
                "required": required,
                "tolerated_faults": f,
            }
        return None

    def verify_chain(self) -> Tuple[bool, Optional[int]]:
        for i in range(1, len(self.blocks)):
            block = self.blocks[i]
            prev = self.blocks[i - 1]
            if block.header.parent_hash != prev.block_hash:
                return False, i
            if block.block_hash != block.header.compute_hash():
                return False, i
        return True, None

    def get_account(self, address: str) -> dict:
        return {
            "address": address,
            "balance_wei": self.state.balances[address],
            "nonce": self.state.nonces[address],
            "reputation": self.state.reputation[address],
        }

    def get_block(self, number: int) -> Optional[Block]:
        if 0 <= number < len(self.blocks):
            return self.blocks[number]
        return None
