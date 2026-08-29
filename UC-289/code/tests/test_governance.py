from governance import RiskGovernanceEngine
from ledger import AuditLedger
from models import *
def engine(**kw):return RiskGovernanceEngine(costs={"S":100},prices={"S":150},**kw)
def action(price,key="k",agent="a",quantity=1):return AgentAction(agent,"org","set_price",{"sku":"S","price":price,"quantity":quantity},"reason",key,"v1")
def test_low_risk_auto_approved():assert engine().evaluate(action(154)).outcome==Outcome.AUTO_APPROVED
def test_floor_and_change_blocked():
 d=engine().evaluate(action(95));assert d.outcome==Outcome.BLOCKED_POLICY and d.risk==RiskLevel.CRITICAL
def test_impact_budget():assert engine().evaluate(action(154,quantity=100000)).outcome==Outcome.BLOCKED_POLICY
def test_approval_and_separation_of_duties():
 e=engine();a=action(160)
 assert e.evaluate(a).outcome==Outcome.APPROVAL_REQUIRED
 e=engine();ap=HumanApproval("manager","director","reviewed impact",True)
 assert e.evaluate(action(160,"x"),ap).outcome==Outcome.APPROVED
 e=engine();bad=HumanApproval("a","agent","self approval",True)
 assert e.evaluate(action(160,"y"),bad).outcome==Outcome.BLOCKED_POLICY
def test_idempotency():
 e=engine();a=action(154);assert e.evaluate(a) is e.evaluate(a);assert len(e.ledger.records())==1
def test_rate_limit():
 e=engine(policy=GovernancePolicy(max_actions_per_hour=1));e.evaluate(action(151,"1"));assert e.evaluate(action(152,"2")).outcome==Outcome.BLOCKED_POLICY
def test_circuit_breaker_and_reset():
 e=engine(policy=GovernancePolicy(circuit_failure_threshold=2));e.evaluate(action(90,"1"));e.evaluate(action(90,"2"));assert e.evaluate(action(150,"3")).outcome==Outcome.CIRCUIT_OPEN;e.reset_circuit("a","operator");assert "a" not in e.circuit_open
def test_hash_chain_verifies():
 e=engine();e.evaluate(action(151,"1"));e.evaluate(action(152,"2"));assert e.ledger.verify();assert len(e.ledger.records()[0]["record_hash"])==64
def test_invalid_action():
 import pytest
 with pytest.raises(ValueError):engine().evaluate(AgentAction("","org","x",{},"","k"))