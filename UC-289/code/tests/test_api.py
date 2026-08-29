import api,pytest
from governance import RiskGovernanceEngine
@pytest.fixture
def client():
 api.engine=RiskGovernanceEngine(costs={"SKU-001":100},prices={"SKU-001":150});api.app.config["TESTING"]=True;return api.app.test_client()
def payload(price=154,key="k"):return {"agent_id":"agent","organization_id":"org","tool":"set_price","params":{"sku":"SKU-001","price":price,"quantity":10},"reasoning":"bounded optimization","idempotency_key":key,"model_version":"v1"}
def test_health_schema(client):assert client.get("/health").status_code==200 and client.get("/api/v1/schema").status_code==200
def test_full_api_and_audit(client):
 r=client.post("/api/v1/governance/evaluate",json=payload());d=r.get_json()["data"];assert d["outcome"]=="auto_approved" and len(d["ledger_hash"])==64
 a=client.get("/api/v1/audit").get_json()["data"];assert a["valid"] and len(a["records"])==1
def test_block_and_approval(client):
 assert client.post("/api/v1/governance/evaluate",json=payload(90,"bad")).get_json()["data"]["outcome"]=="blocked_policy"
 d=payload(160,"approve");d["approval"]={"approver_id":"manager","role":"director","justification":"impact reviewed","approved":True}
 assert client.post("/api/v1/governance/evaluate",json=d).get_json()["data"]["outcome"]=="approved"
def test_validation(client):assert client.post("/api/v1/governance/evaluate",json={}).status_code==400