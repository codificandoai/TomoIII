"""Tests del motor de consenso BFT."""
from __future__ import annotations

from blockchain import Block, Blockchain
from consensus import BFTConsensusEngine
from wallet import Wallet


def test_consensus_with_honest_validators():
    validators = [Wallet() for _ in range(4)]
    engine = BFTConsensusEngine(validators)
    bc = Blockchain(validators)
    bc.mint(validators[0].address, 10000)

    from blockchain import Transaction
    from models import TransactionType
    tx = Transaction(
        nonce=0, from_address=validators[0].address,
        to_address=validators[1].address,
        tx_type=TransactionType.transfer, value_wei=100
    ).sign_with(validators[0])
    bc.submit_transaction(tx)

    block = bc.propose_and_commit_block(validators[0], engine)
    assert block is not None
    assert block.header.consensus_proof["type"] == "bft_final"


def test_consensus_tolerates_one_byzantine():
    validators = [Wallet() for _ in range(4)]
    byzantine = {validators[3].address}
    engine = BFTConsensusEngine(validators, byzantine)
    bc = Blockchain(validators)
    bc.mint(validators[0].address, 10000)

    from blockchain import Transaction
    from models import TransactionType
    tx = Transaction(
        nonce=0, from_address=validators[0].address,
        to_address=validators[1].address,
        tx_type=TransactionType.transfer, value_wei=50
    ).sign_with(validators[0])
    bc.submit_transaction(tx)

    block = bc.propose_and_commit_block(validators[0], engine)
    # With 4 validators and f=1, we need 3 votes. 3 honest should suffice.
    assert block is not None


def test_consensus_count():
    validators = [Wallet() for _ in range(4)]
    engine = BFTConsensusEngine(validators)
    assert engine.consensus_count == 0

    bc = Blockchain(validators)
    bc.mint(validators[0].address, 10000)

    from blockchain import Transaction
    from models import TransactionType
    tx = Transaction(
        nonce=0, from_address=validators[0].address,
        to_address=validators[1].address,
        tx_type=TransactionType.transfer, value_wei=10
    ).sign_with(validators[0])
    bc.submit_transaction(tx)
    bc.propose_and_commit_block(validators[0], engine)

    assert engine.consensus_count >= 1
