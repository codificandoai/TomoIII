"""Motor de consenso PBFT-lite para UC-274.

Implementa el protocolo BFT completo:
1. PRE-PREPARE: proposer envía bloque a todos los validadores.
2. PREPARE: validadores verifican y votan.
3. COMMIT: tras recibir 2f+1 PREPARE, envía COMMIT.
4. DECIDE: tras 2f+1 COMMIT, bloque es final.

Tolerancia: f fallos byzantinos con n = 3f+1 validadores.
Soporta simulación de validadores byzantinos.
"""
from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from wallet import Wallet
from blockchain import Block


@dataclass
class BFTMessage:
    """Mensaje del protocolo BFT."""
    phase: str  # pre_prepare, prepare, commit
    block_hash: str
    block_number: int
    sender: str
    signature: bytes
    timestamp: float = field(default_factory=time.time)


class BFTConsensusEngine:
    """
    Motor de consenso PBFT-lite.
    Tolerancia: f fallos byzantinos con n = 3f+1 validadores.
    """

    def __init__(self, validators: List[Wallet],
                 byzantine_validators: Optional[Set[str]] = None) -> None:
        self.validators = validators
        self.n = len(validators)
        self.f = (self.n - 1) // 3
        self.required = 2 * self.f + 1
        self.byzantine = byzantine_validators or set()
        self.prepares: Dict[str, Dict[str, bytes]] = defaultdict(dict)
        self.commits: Dict[str, Dict[str, bytes]] = defaultdict(dict)
        self.decided: Set[str] = set()
        self.history: List[dict] = []

    def run_full_protocol(self, block: Block, proposer: Wallet) -> Optional[dict]:
        """Ejecuta protocolo BFT completo (4 fases)."""
        block_hash = block.block_hash

        # FASE 1: PRE-PREPARE (proposer broadcast)
        self._create_message("pre_prepare", block, proposer)

        # FASE 2: PREPARE (cada validador vota)
        for validator in self.validators:
            if validator.address == proposer.address:
                continue

            if validator.address in self.byzantine:
                # Byzantine: comportamiento adversarial
                if hash(block_hash + validator.address) % 3 == 0:
                    continue  # no vota
                fake_hash = hashlib.sha256(
                    (block_hash + "fake").encode()
                ).hexdigest()
                self.prepares[fake_hash][validator.address] = b"fake"
                continue

            # Validador honesto
            if self._validate_block(block):
                msg = self._create_message("prepare", block, validator)
                self.prepares[block_hash][validator.address] = msg.signature

        if len(self.prepares[block_hash]) < self.required - 1:
            return None

        # FASE 3: COMMIT
        for validator in self.validators:
            if validator.address in self.byzantine:
                if hash(block_hash + validator.address) % 2 == 0:
                    continue

            msg = self._create_message("commit", block, validator)
            self.commits[block_hash][validator.address] = msg.signature

        if len(self.commits[block_hash]) < self.required:
            return None

        # FASE 4: DECIDE
        self.decided.add(block_hash)

        proof = {
            "type": "bft_final",
            "block_hash": block_hash,
            "prepares": len(self.prepares[block_hash]),
            "commits": len(self.commits[block_hash]),
            "quorum": len(self.commits[block_hash]),
            "required": self.required,
            "f": self.f,
            "byzantine_tolerated": len(self.byzantine),
        }
        self.history.append(proof)
        return proof

    def _create_message(self, phase: str, block: Block,
                        signer: Wallet) -> BFTMessage:
        content = f"{phase}|{block.block_hash}|{block.header.block_number}"
        signature = signer.sign(content.encode("utf-8"))
        return BFTMessage(
            phase=phase,
            block_hash=block.block_hash,
            block_number=block.header.block_number,
            sender=signer.address,
            signature=signature,
        )

    def _validate_block(self, block: Block) -> bool:
        return block.block_hash == block.header.compute_hash()

    @property
    def consensus_count(self) -> int:
        return len(self.decided)
