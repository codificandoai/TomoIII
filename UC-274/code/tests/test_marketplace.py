"""Tests del Energy Marketplace P2P."""
from __future__ import annotations

from marketplace import EnergyMarketplace


def _mp():
    return EnergyMarketplace()


def test_register_agent():
    mp = _mp()
    result = mp.register_agent("solar_1", 1_000_000, {"role": "prosumer"})
    assert result["name"] == "solar_1"
    assert result["address"].startswith("0x")
    assert result["did"].startswith("did:mustiamente:")
    assert result["balance_wei"] == 1_000_000


def test_register_duplicate_agent():
    mp = _mp()
    mp.register_agent("dup", 100)
    try:
        mp.register_agent("dup", 100)
        assert False, "Should raise ValueError"
    except ValueError:
        pass


def test_get_agent():
    mp = _mp()
    mp.register_agent("test_agent", 500_000)
    agent = mp.get_agent("test_agent")
    assert agent is not None
    assert agent["balance_wei"] == 500_000


def test_list_agents():
    mp = _mp()
    mp.register_agent("a1", 100)
    mp.register_agent("a2", 200)
    agents = mp.list_agents()
    assert len(agents) == 2


def test_energy_offer_and_trade():
    mp = _mp()
    mp.register_agent("seller", 1_000_000)
    mp.register_agent("buyer", 1_000_000)

    offer = mp.create_energy_offer("seller", "sell", 50.0, 1000, "solar")
    assert "offer_id" in offer

    trade = mp.match_trade("buyer", offer["offer_id"], 20.0)
    assert trade["status"] == "escrow_locked"


def test_confirm_delivery():
    mp = _mp()
    mp.register_agent("seller", 1_000_000)
    mp.register_agent("buyer", 1_000_000)

    offer = mp.create_energy_offer("seller", "sell", 50.0, 1000)
    trade = mp.match_trade("buyer", offer["offer_id"], 10.0)

    delivery = mp.confirm_delivery(trade["trade_id"])
    assert delivery["status"] == "delivered"


def test_escrow():
    mp = _mp()
    mp.register_agent("dep", 1_000_000)
    mp.register_agent("ben", 100)

    escrow = mp.create_escrow("dep", "ben", 50_000, "deliver goods")
    assert escrow["status"] == "locked"


def test_reputation():
    mp = _mp()
    mp.register_agent("trader_1", 100)

    result = mp.record_trade_reputation("trader_1", True)
    assert result["reputation"] > 0.5

    rep = mp.get_reputation("trader_1")
    assert rep["total_trades"] == 1


def test_endorsement():
    mp = _mp()
    mp.register_agent("endorser", 100)
    mp.register_agent("target", 100)

    result = mp.endorse_agent("endorser", "target", 0.8)
    assert "new_reputation" in result


def test_chain_status():
    mp = _mp()
    status = mp.get_chain_status()
    assert status["block_height"] == 0
    assert status["validator_count"] == 4
    assert status["chain_valid"] is True


def test_marketplace_status():
    mp = _mp()
    mp.register_agent("a", 100)
    status = mp.get_marketplace_status()
    assert status["total_agents"] == 1


def test_verify_chain():
    mp = _mp()
    result = mp.verify_chain()
    assert result["valid"] is True
