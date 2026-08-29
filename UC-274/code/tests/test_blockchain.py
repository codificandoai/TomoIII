"""Tests de la blockchain PoA."""
from __future__ import annotations

from blockchain import Block, Blockchain, BlockchainState, Transaction
from models import TransactionType
from wallet import DID, DIDRegistry, Wallet


def _chain():
    validators = [Wallet() for _ in range(4)]
    reg = DIDRegistry()
    for v in validators:
        did = DID.create(v)
        reg.register(did)
    bc = Blockchain(validators, reg)
    return bc, validators


def test_genesis_block():
    bc, _ = _chain()
    assert bc.block_height == 0
    assert bc.blocks[0].header.block_number == 0
    assert bc.blocks[0].header.consensus_proof["type"] == "genesis"


def test_mint():
    bc, validators = _chain()
    bc.mint(validators[0].address, 1_000_000)
    assert bc.state.balances[validators[0].address] == 1_000_000


def test_submit_and_mine_block():
    bc, validators = _chain()
    bc.mint(validators[0].address, 1_000_000)

    tx = Transaction(
        nonce=0,
        from_address=validators[0].address,
        to_address=validators[1].address,
        tx_type=TransactionType.transfer,
        value_wei=500,
    )
    tx = tx.sign_with(validators[0])
    bc.submit_transaction(tx)

    block = bc.propose_and_commit_block(validators[0])
    assert block is not None
    assert block.header.block_number == 1
    assert len(block.transactions) == 1


def test_transfer_updates_balances():
    bc, validators = _chain()
    bc.mint(validators[0].address, 10000)

    tx = Transaction(
        nonce=0,
        from_address=validators[0].address,
        to_address=validators[1].address,
        tx_type=TransactionType.transfer,
        value_wei=3000,
    )
    tx = tx.sign_with(validators[0])
    bc.submit_transaction(tx)
    bc.propose_and_commit_block(validators[0])

    assert bc.state.balances[validators[0].address] == 7000
    assert bc.state.balances[validators[1].address] == 3000


def test_insufficient_balance_rejected():
    bc, validators = _chain()
    bc.mint(validators[0].address, 100)

    tx = Transaction(
        nonce=0,
        from_address=validators[0].address,
        to_address=validators[1].address,
        tx_type=TransactionType.transfer,
        value_wei=999999,
    )
    tx = tx.sign_with(validators[0])
    bc.submit_transaction(tx)

    block = bc.propose_and_commit_block(validators[0])
    assert block is None  # transaction rejected


def test_verify_chain():
    bc, validators = _chain()
    bc.mint(validators[0].address, 10000)

    tx = Transaction(
        nonce=0,
        from_address=validators[0].address,
        to_address=validators[1].address,
        tx_type=TransactionType.transfer,
        value_wei=100,
    )
    tx = tx.sign_with(validators[0])
    bc.submit_transaction(tx)
    bc.propose_and_commit_block(validators[0])

    valid, broken = bc.verify_chain()
    assert valid is True
    assert broken is None


def test_merkle_root():
    w = Wallet()
    txs = [
        Transaction(nonce=i, from_address=w.address, tx_type=TransactionType.transfer).sign_with(w)
        for i in range(5)
    ]
    root = Block._compute_tx_root(txs)
    assert len(root) == 64  # SHA-256 hex


def test_get_account():
    bc, validators = _chain()
    bc.mint(validators[0].address, 42000)
    acct = bc.get_account(validators[0].address)
    assert acct["balance_wei"] == 42000
    assert acct["nonce"] == 0


def test_state_copy():
    state = BlockchainState()
    state.balances["a"] = 100
    state.nonces["a"] = 5
    state.reputation["a"] = 0.8

    copy = state.copy()
    copy.balances["a"] = 999
    assert state.balances["a"] == 100  # original unchanged
