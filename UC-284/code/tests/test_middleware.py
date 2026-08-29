import pytest
from memory import HybridMemory
from middleware import ResilientAgentMiddleware
from models import AgentRequest,Constitution

def request(price=255,execute=False,approved=False,facts=None):
    return AgentRequest("Protect profit and trust","SKU",250,price,facts if facts is not None else {"SKU_cost":150,"competitor_price":245},"pricing",execute,approved)

def test_valid_pipeline():
    ctx=ResilientAgentMiddleware().process(request())
    assert ctx.status=="validated" and ctx.final_price==255
    assert [s["status"] for s in ctx.stages]==["pass"]*6
    assert len(ctx.audit_hash())==64

def test_missing_grounding_blocks():
    ctx=ResilientAgentMiddleware().process(request(facts={}))
    assert ctx.status=="blocked" and "missing grounded" in ctx.errors[0]

def test_margin_guard_blocks():
    ctx=ResilientAgentMiddleware().process(request(price=160))
    assert ctx.status=="blocked" and "margin" in ctx.errors[0]

def test_change_guard_blocks():
    ctx=ResilientAgentMiddleware().process(request(price=280))
    assert ctx.status=="blocked"

def test_approval_gate():
    p=ResilientAgentMiddleware(constitution=Constitution(max_price_change=.1,approval_price_change=.01))
    assert p.process(request(255,True,False)).status=="approval_required"
    assert p.process(request(255,True,True)).status=="executed"

def test_memory_retrieval_and_reconciliation():
    m=HybridMemory(); m.remember("pricing customer trust lesson","semantic",.9)
    m.upsert_fact("x",1,"weak",.2); m.upsert_fact("x",2,"strong",.9); m.upsert_fact("x",3,"weaker",.3)
    assert m.facts()["x"]["value"]=="2"
    ctx=ResilientAgentMiddleware(m).process(request())
    assert ctx.memories

def test_context_budget():
    m=HybridMemory(); m.remember("x"*1000)
    ctx=ResilientAgentMiddleware(m,Constitution(context_budget_chars=100)).process(request())
    assert len(ctx.compact_context)<=100

def test_invalid_request():
    with pytest.raises(ValueError): ResilientAgentMiddleware().process(AgentRequest("","",1,1))