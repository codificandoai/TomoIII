"""Flask governance API with input/output cards."""
from flask import Flask,jsonify,request
from governance import RiskGovernanceEngine
from ledger import AuditLedger
from models import AgentAction,HumanApproval
app=Flask(__name__);engine=RiskGovernanceEngine(costs={"SKU-001":100},prices={"SKU-001":150})
INPUT_CARDS=[{"endpoint":"POST /api/v1/governance/evaluate","parameters":[{"name":"agent_id","type":"string","required":True},{"name":"organization_id","type":"string","required":True},{"name":"tool","type":"string","required":True},{"name":"params","type":"object","required":True},{"name":"reasoning","type":"string","required":True},{"name":"idempotency_key","type":"string","required":True},{"name":"model_version","type":"string","required":False},{"name":"approval","type":"object","required":False}]}]
OUTPUT_CARDS=[{"endpoint":"POST /api/v1/governance/evaluate","fields":[{"name":"decision_id","type":"string"},{"name":"risk","type":"string"},{"name":"outcome","type":"string"},{"name":"reasons","type":"array"},{"name":"accountable_role","type":"string"},{"name":"policy_version","type":"string"},{"name":"ledger_hash","type":"sha256"}]}]
def ok(data,status=200):return jsonify({"status":"ok","data":data}),status
def error(msg,status=400):return jsonify({"status":"error","message":msg}),status
@app.errorhandler(ValueError)
def bad(e):return error(str(e))
@app.get("/health")
def health():return ok({"service":"uc289-agent-governance","ready":True,**engine.status()})
@app.get("/api/v1/schema")
def schema():return ok({"input_cards":INPUT_CARDS,"output_cards":OUTPUT_CARDS})
@app.post("/api/v1/governance/evaluate")
def evaluate():
 d=request.get_json(silent=True) or {};required=["agent_id","organization_id","tool","params","reasoning","idempotency_key"];missing=[k for k in required if k not in d]
 if missing:return error(f"Missing required fields: {', '.join(missing)}")
 a=AgentAction(str(d["agent_id"]),str(d["organization_id"]),str(d["tool"]),d["params"],str(d["reasoning"]),str(d["idempotency_key"]),str(d.get("model_version","unknown")))
 ap=HumanApproval(**d["approval"]) if d.get("approval") else None;decision=engine.evaluate(a,ap);out=decision.public_dict();out["ledger_hash"]=decision.ledger_hash;return ok(out)
@app.get("/api/v1/governance/status")
def status():return ok(engine.status())
@app.get("/api/v1/audit")
def audit():return ok({"valid":engine.ledger.verify(),"records":engine.ledger.records(min(100,int(request.args.get("limit",50))))})
@app.post("/api/v1/circuits/<agent_id>/reset")
def reset(agent_id):
 d=request.get_json(silent=True) or {};engine.reset_circuit(agent_id,str(d.get("operator_id","")));return ok(engine.status())
if __name__=="__main__":app.run(host="0.0.0.0",port=5289,debug=False)