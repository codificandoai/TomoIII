import pytest,api
from memory import HybridMemory
from middleware import ResilientAgentMiddleware
@pytest.fixture
def client():
    api.memory=HybridMemory(); api.middleware=ResilientAgentMiddleware(api.memory); api.app.config["TESTING"]=True; return api.app.test_client()
def payload(): return {"objective":"Optimize safely","sku":"SKU","current_price":250,"proposed_price":255,"facts":{"SKU_cost":150,"competitor_price":245}}
def test_health_schema(client):
    assert client.get("/health").status_code==200
    assert client.get("/api/v1/schema").get_json()["data"]["input_cards"]
def test_process_and_memory(client):
    r=client.post("/api/v1/middleware/process",json=payload()); d=r.get_json()["data"]
    assert r.status_code==200 and d["status"]=="validated" and len(d["audit_hash"])==64
    assert client.get("/api/v1/memory").get_json()["data"]["stats"]["facts"]==2
def test_validation(client):
    assert client.post("/api/v1/middleware/process",json={}).status_code==400
    d=payload();d["proposed_price"]=-1
    assert client.post("/api/v1/middleware/process",json=d).status_code==400