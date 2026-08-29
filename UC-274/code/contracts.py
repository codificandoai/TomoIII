"""Smart Contracts para UC-274 — Web3 Multi-Agent.

Implementa 4 contratos inteligentes:
1. EnergyTradeContract: comercio P2P de energía entre prosumidores.
2. EscrowContract: pagos condicionales con timeout.
3. ReputationContract: reputación on-chain con decay bayesiano.
4. SettlementContract: liquidación de trades con fees.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from blockchain import BlockchainState, Transaction


class SmartContract:
    """Contrato inteligente base."""

    def __init__(self, address: str, deployer: str,
                 state: BlockchainState, init_params: dict) -> None:
        self.address = address
        self.deployer = deployer
        self.state = state
        self.contract_state: Dict[str, Any] = dict(init_params)
        self.state.contracts[address] = self.contract_state

    def execute(self, tx: Transaction) -> dict:
        method = tx.data.get("method")
        args = tx.data.get("args", {})
        handler = getattr(self, f"method_{method}", None)
        if not handler:
            return {"error": f"Unknown method: {method}"}
        result = handler(tx.from_address, **args)
        self.state.contracts[self.address] = self.contract_state
        return result

    def _save(self) -> None:
        self.state.contracts[self.address] = self.contract_state

    @staticmethod
    def compute_address(deployer: str, nonce: int, tx_id: str) -> str:
        return "0x" + hashlib.sha256(
            f"{deployer}:{nonce}:{tx_id}".encode()
        ).hexdigest()[:40]


class EnergyTradeContract(SmartContract):
    """Contrato para comercio descentralizado de energía P2P.

    Permite prosumidores publicar ofertas de venta/compra, matching
    automático, settlement con escrow y medición verificada por oracles.
    """

    def __init__(self, address: str, deployer: str,
                 state: BlockchainState, init_params: dict) -> None:
        super().__init__(address, deployer, state, init_params)
        self.contract_state.setdefault("offers", {})
        self.contract_state.setdefault("trades", {})
        self.contract_state.setdefault("balances_kwh", {})
        self.contract_state.setdefault("oracles", [deployer])
        self.contract_state.setdefault("fee_bps", init_params.get("fee_bps", 50))

    def method_create_offer(self, creator: str, side: str = "sell",
                            quantity_kwh: float = 10.0,
                            price_per_kwh_wei: int = 1000,
                            delivery_window: list | None = None,
                            energy_source: str = "solar") -> dict:
        offer_id = uuid4().hex[:16]
        offer = {
            "offer_id": offer_id,
            "creator": creator,
            "side": side,
            "quantity_kwh": quantity_kwh,
            "remaining_kwh": quantity_kwh,
            "price_per_kwh_wei": price_per_kwh_wei,
            "delivery_window": delivery_window or [],
            "energy_source": energy_source,
            "created_at": time.time(),
            "status": "open",
        }
        self.contract_state["offers"][offer_id] = offer
        self._save()
        return {"offer_id": offer_id, "status": "created"}

    def method_match_and_trade(self, buyer: str, offer_id: str = "",
                               quantity_kwh: float = 0.0) -> dict:
        offer = self.contract_state["offers"].get(offer_id)
        if not offer:
            return {"error": "offer_not_found"}
        if offer["status"] != "open":
            return {"error": "offer_not_open"}
        if offer["side"] != "sell":
            return {"error": "cannot_buy_from_buy_offer"}
        if quantity_kwh > offer["remaining_kwh"]:
            return {"error": "insufficient_quantity"}

        total_wei = int(quantity_kwh * offer["price_per_kwh_wei"])
        if self.state.balances[buyer] < total_wei:
            return {"error": "insufficient_balance"}

        # Escrow
        self.state.balances[buyer] -= total_wei
        escrow_key = f"escrow:{buyer}:{offer_id}"
        self.contract_state[escrow_key] = {
            "buyer": buyer,
            "seller": offer["creator"],
            "amount_wei": total_wei,
            "quantity_kwh": quantity_kwh,
            "status": "locked",
            "created_at": time.time(),
        }

        offer["remaining_kwh"] -= quantity_kwh
        if offer["remaining_kwh"] <= 0.001:
            offer["status"] = "filled"

        trade_id = uuid4().hex[:16]
        trade = {
            "trade_id": trade_id,
            "buyer": buyer,
            "seller": offer["creator"],
            "quantity_kwh": quantity_kwh,
            "price_per_kwh_wei": offer["price_per_kwh_wei"],
            "total_wei": total_wei,
            "energy_source": offer["energy_source"],
            "status": "pending_delivery",
            "created_at": time.time(),
        }
        self.contract_state["trades"][trade_id] = trade
        self._save()
        return {"trade_id": trade_id, "status": "escrow_locked", "total_wei": total_wei}

    def method_confirm_delivery(self, caller: str, trade_id: str = "") -> dict:
        """Oracle confirma entrega de energía y libera escrow."""
        if caller not in self.contract_state["oracles"]:
            return {"error": "unauthorized_oracle"}

        trade = self.contract_state["trades"].get(trade_id)
        if not trade:
            return {"error": "trade_not_found"}
        if trade["status"] != "pending_delivery":
            return {"error": "trade_not_pending"}

        # Libera escrow
        escrow_key = None
        for k in list(self.contract_state.keys()):
            if k.startswith("escrow:") and k.endswith(trade.get("_offer_id", "")):
                escrow_key = k
                break

        # Calcula fee
        fee_bps = self.contract_state.get("fee_bps", 50)
        fee = trade["total_wei"] * fee_bps // 10000
        seller_amount = trade["total_wei"] - fee

        self.state.balances[trade["seller"]] += seller_amount
        trade["status"] = "delivered"
        trade["fee_wei"] = fee

        # Actualiza reputación
        self.state.reputation[trade["seller"]] = min(
            1.0, self.state.reputation[trade["seller"]] + 0.01
        )
        self.state.reputation[trade["buyer"]] = min(
            1.0, self.state.reputation[trade["buyer"]] + 0.005
        )

        self._save()
        return {"trade_id": trade_id, "status": "delivered", "seller_received": seller_amount, "fee": fee}

    def get_offers(self, status: str = "open") -> List[dict]:
        return [o for o in self.contract_state["offers"].values() if o["status"] == status]

    def get_trades(self) -> List[dict]:
        return list(self.contract_state["trades"].values())


class EscrowContract(SmartContract):
    """Contrato de pagos condicionales con timeout."""

    def __init__(self, address: str, deployer: str,
                 state: BlockchainState, init_params: dict) -> None:
        super().__init__(address, deployer, state, init_params)
        self.contract_state.setdefault("escrows", {})
        self.contract_state.setdefault("timeout_seconds", init_params.get("timeout_seconds", 86400))

    def method_deposit(self, depositor: str, beneficiary: str = "",
                       amount_wei: int = 0, condition: str = "") -> dict:
        if self.state.balances[depositor] < amount_wei:
            return {"error": "insufficient_balance"}

        escrow_id = uuid4().hex[:16]
        self.state.balances[depositor] -= amount_wei

        timeout = self.contract_state["timeout_seconds"]
        escrow = {
            "escrow_id": escrow_id,
            "depositor": depositor,
            "beneficiary": beneficiary,
            "amount_wei": amount_wei,
            "condition": condition,
            "status": "locked",
            "created_at": time.time(),
            "timeout_at": time.time() + timeout,
        }
        self.contract_state["escrows"][escrow_id] = escrow
        self._save()
        return {"escrow_id": escrow_id, "status": "locked"}

    def method_release(self, caller: str, escrow_id: str = "") -> dict:
        escrow = self.contract_state["escrows"].get(escrow_id)
        if not escrow:
            return {"error": "escrow_not_found"}
        if escrow["status"] != "locked":
            return {"error": "escrow_not_locked"}
        if caller != escrow["depositor"] and caller != self.deployer:
            return {"error": "unauthorized"}

        self.state.balances[escrow["beneficiary"]] += escrow["amount_wei"]
        escrow["status"] = "released"
        self._save()
        return {"escrow_id": escrow_id, "status": "released", "beneficiary": escrow["beneficiary"]}

    def method_refund(self, caller: str, escrow_id: str = "") -> dict:
        escrow = self.contract_state["escrows"].get(escrow_id)
        if not escrow:
            return {"error": "escrow_not_found"}
        if escrow["status"] != "locked":
            return {"error": "escrow_not_locked"}

        # Solo refund si expiró o si lo solicita el beneficiario/deployer
        if caller not in (escrow["beneficiary"], self.deployer):
            if time.time() < escrow["timeout_at"]:
                return {"error": "escrow_not_expired"}

        self.state.balances[escrow["depositor"]] += escrow["amount_wei"]
        escrow["status"] = "refunded"
        self._save()
        return {"escrow_id": escrow_id, "status": "refunded"}

    def get_escrows(self, status: str | None = None) -> List[dict]:
        escrows = self.contract_state["escrows"].values()
        if status:
            return [e for e in escrows if e["status"] == status]
        return list(escrows)


class ReputationContract(SmartContract):
    """Contrato de reputación on-chain con actualización bayesiana."""

    def __init__(self, address: str, deployer: str,
                 state: BlockchainState, init_params: dict) -> None:
        super().__init__(address, deployer, state, init_params)
        self.contract_state.setdefault("records", {})
        self.contract_state.setdefault("endorsements", [])

    def method_record_trade(self, caller: str, trader: str = "",
                            success: bool = True) -> dict:
        if trader not in self.contract_state["records"]:
            self.contract_state["records"][trader] = {
                "total_trades": 0,
                "successful_trades": 0,
                "disputes": 0,
            }
        rec = self.contract_state["records"][trader]
        rec["total_trades"] += 1
        if success:
            rec["successful_trades"] += 1
            self.state.reputation[trader] = min(1.0, self.state.reputation[trader] + 0.02)
        else:
            rec["disputes"] += 1
            self.state.reputation[trader] = max(0.0, self.state.reputation[trader] - 0.05)

        self._save()
        return {"trader": trader, "reputation": round(self.state.reputation[trader], 4),
                "total_trades": rec["total_trades"]}

    def method_endorse(self, endorser: str, target: str = "",
                       score: float = 1.0) -> dict:
        if endorser == target:
            return {"error": "cannot_self_endorse"}

        endorser_rep = self.state.reputation[endorser]
        weight = endorser_rep * 0.01 * min(1.0, max(0.0, score))
        self.state.reputation[target] = min(1.0, self.state.reputation[target] + weight)

        self.contract_state["endorsements"].append({
            "endorser": endorser,
            "target": target,
            "score": score,
            "weight": round(weight, 6),
            "timestamp": time.time(),
        })
        self._save()
        return {"target": target, "new_reputation": round(self.state.reputation[target], 4),
                "weight_applied": round(weight, 6)}

    def get_reputation(self, address: str) -> dict:
        rec = self.contract_state["records"].get(address, {})
        return {
            "address": address,
            "reputation": round(self.state.reputation[address], 4),
            "total_trades": rec.get("total_trades", 0),
            "successful_trades": rec.get("successful_trades", 0),
            "disputes": rec.get("disputes", 0),
        }


class SettlementContract(SmartContract):
    """Contrato de liquidación de trades con fees."""

    def __init__(self, address: str, deployer: str,
                 state: BlockchainState, init_params: dict) -> None:
        super().__init__(address, deployer, state, init_params)
        self.contract_state.setdefault("settlements", {})
        self.contract_state.setdefault("fee_bps", init_params.get("fee_bps", 30))
        self.contract_state.setdefault("total_fees_collected", 0)

    def method_settle(self, caller: str, buyer: str = "", seller: str = "",
                      amount_wei: int = 0, trade_ref: str = "") -> dict:
        if caller != self.deployer:
            return {"error": "only_deployer_can_settle"}

        fee_bps = self.contract_state["fee_bps"]
        fee = amount_wei * fee_bps // 10000
        net = amount_wei - fee

        self.state.balances[seller] += net
        self.contract_state["total_fees_collected"] += fee

        settlement_id = uuid4().hex[:16]
        settlement = {
            "settlement_id": settlement_id,
            "buyer": buyer,
            "seller": seller,
            "gross_amount": amount_wei,
            "fee": fee,
            "net_amount": net,
            "trade_ref": trade_ref,
            "settled_at": time.time(),
        }
        self.contract_state["settlements"][settlement_id] = settlement
        self._save()
        return {"settlement_id": settlement_id, "net_amount": net, "fee": fee}

    def get_settlements(self) -> List[dict]:
        return list(self.contract_state["settlements"].values())

    def get_fee_summary(self) -> dict:
        return {
            "total_settlements": len(self.contract_state["settlements"]),
            "total_fees_collected": self.contract_state["total_fees_collected"],
            "fee_bps": self.contract_state["fee_bps"],
        }


def deploy_contract(contract_type: str, deployer: str,
                    state: BlockchainState, init_params: dict,
                    tx_id: str = "", nonce: int = 0) -> Optional[SmartContract]:
    """Factory para desplegar contratos."""
    factory = {
        "energy_trade": EnergyTradeContract,
        "escrow": EscrowContract,
        "reputation": ReputationContract,
        "settlement": SettlementContract,
    }
    cls = factory.get(contract_type)
    if not cls:
        return None

    address = SmartContract.compute_address(deployer, nonce, tx_id or uuid4().hex)
    return cls(address=address, deployer=deployer, state=state, init_params=init_params)
