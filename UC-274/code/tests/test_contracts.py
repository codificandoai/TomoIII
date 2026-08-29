"""Tests de Smart Contracts."""
from __future__ import annotations

from blockchain import BlockchainState
from contracts import (
    EnergyTradeContract,
    EscrowContract,
    ReputationContract,
    SettlementContract,
    deploy_contract,
)
from wallet import Wallet


def _state_with_balance(address: str, balance: int = 1_000_000) -> BlockchainState:
    state = BlockchainState()
    state.balances[address] = balance
    return state


# --- Energy Trade ---

def test_create_offer():
    state = _state_with_balance("seller_1")
    contract = EnergyTradeContract("0xE", "deployer", state, {"fee_bps": 50})

    result = contract.method_create_offer("seller_1", side="sell", quantity_kwh=50.0,
                                          price_per_kwh_wei=1000, energy_source="solar")
    assert result["status"] == "created"
    assert "offer_id" in result


def test_match_and_trade():
    state = _state_with_balance("buyer_1", 100_000)
    contract = EnergyTradeContract("0xE", "deployer", state, {"fee_bps": 50})

    offer = contract.method_create_offer("seller_1", side="sell", quantity_kwh=50.0,
                                         price_per_kwh_wei=1000)
    trade = contract.method_match_and_trade("buyer_1", offer_id=offer["offer_id"],
                                            quantity_kwh=20.0)
    assert trade["status"] == "escrow_locked"
    assert trade["total_wei"] == 20000


def test_match_insufficient_balance():
    state = _state_with_balance("poor_buyer", 10)
    contract = EnergyTradeContract("0xE", "deployer", state, {"fee_bps": 50})

    offer = contract.method_create_offer("seller_1", side="sell", quantity_kwh=50.0,
                                         price_per_kwh_wei=1000)
    result = contract.method_match_and_trade("poor_buyer", offer_id=offer["offer_id"],
                                             quantity_kwh=20.0)
    assert result["error"] == "insufficient_balance"


def test_confirm_delivery():
    state = _state_with_balance("buyer_1", 100_000)
    contract = EnergyTradeContract("0xE", "deployer", state,
                                   {"fee_bps": 50, "oracles": ["oracle_1"]})

    offer = contract.method_create_offer("seller_1", side="sell", quantity_kwh=50.0,
                                         price_per_kwh_wei=1000)
    trade = contract.method_match_and_trade("buyer_1", offer_id=offer["offer_id"],
                                            quantity_kwh=10.0)
    delivery = contract.method_confirm_delivery("oracle_1", trade_id=trade["trade_id"])
    assert delivery["status"] == "delivered"
    assert delivery["fee"] >= 0


# --- Escrow ---

def test_escrow_deposit_and_release():
    state = _state_with_balance("depositor", 500_000)
    contract = EscrowContract("0xEsc", "deployer", state, {"timeout_seconds": 3600})

    result = contract.method_deposit("depositor", beneficiary="beneficiary",
                                     amount_wei=100_000, condition="deliver goods")
    assert result["status"] == "locked"

    release = contract.method_release("depositor", escrow_id=result["escrow_id"])
    assert release["status"] == "released"
    assert state.balances["beneficiary"] == 100_000


def test_escrow_insufficient_balance():
    state = _state_with_balance("poor", 10)
    contract = EscrowContract("0xEsc", "deployer", state, {})

    result = contract.method_deposit("poor", beneficiary="ben", amount_wei=1000)
    assert result["error"] == "insufficient_balance"


def test_escrow_refund():
    state = _state_with_balance("dep", 500_000)
    contract = EscrowContract("0xEsc", "deployer", state, {"timeout_seconds": -1})  # already expired

    result = contract.method_deposit("dep", beneficiary="ben", amount_wei=50_000)
    refund = contract.method_refund("dep", escrow_id=result["escrow_id"])
    # depositor can refund expired escrow
    assert refund["status"] == "refunded"
    assert state.balances["dep"] == 500_000


# --- Reputation ---

def test_reputation_record_success():
    state = BlockchainState()
    contract = ReputationContract("0xRep", "deployer", state, {})

    result = contract.method_record_trade("deployer", trader="trader_1", success=True)
    assert result["reputation"] > 0.5
    assert result["total_trades"] == 1


def test_reputation_record_failure():
    state = BlockchainState()
    contract = ReputationContract("0xRep", "deployer", state, {})

    result = contract.method_record_trade("deployer", trader="bad_trader", success=False)
    assert result["reputation"] < 0.5


def test_reputation_endorse():
    state = BlockchainState()
    state.reputation["endorser_1"] = 0.9
    contract = ReputationContract("0xRep", "deployer", state, {})

    result = contract.method_endorse("endorser_1", target="target_1", score=1.0)
    assert result["new_reputation"] > 0.5


def test_reputation_self_endorse_rejected():
    state = BlockchainState()
    contract = ReputationContract("0xRep", "deployer", state, {})

    result = contract.method_endorse("self_1", target="self_1")
    assert result["error"] == "cannot_self_endorse"


# --- Settlement ---

def test_settlement():
    state = BlockchainState()
    contract = SettlementContract("0xSettl", "deployer", state, {"fee_bps": 100})

    result = contract.method_settle("deployer", buyer="b", seller="s",
                                    amount_wei=100_000, trade_ref="t1")
    assert result["net_amount"] == 99_000
    assert result["fee"] == 1000


# --- Factory ---

def test_deploy_contract_factory():
    state = BlockchainState()
    c = deploy_contract("energy_trade", "deployer", state, {"fee_bps": 50})
    assert c is not None
    assert c.address.startswith("0x")


def test_deploy_unknown_contract():
    state = BlockchainState()
    c = deploy_contract("unknown", "deployer", state, {})
    assert c is None
