"""Flask API and cards for the resilient middleware."""
from flask import Flask,jsonify,request
from memory import HybridMemory
from middleware import ResilientAgentMiddleware
from models import AgentRequest,Constitution

app=Flask(__name__); memory=HybridMemory(); middleware=ResilientAgentMiddleware(memory)
INPUT_CARDS=[{"endpoint":"POST /api/v1/middleware/process","parameters":[{"name":"objective","type":"string","required":True},{"name":"sku","type":"string","required":True},{"name":"current_price","type":"number","required":True},{"name":"proposed_price","type":"number","required":True},{"name":"facts","type":"object","required":True,"example":{"SKU-001_cost":150,"competitor_price":245}},{"name":"query","type":"string","required":False},{"name":"execute","type":"boolean","required":False},{"name":"approved","type":"boolean","required":False}]}]
OUTPUT_CARDS=[{"endpoint":"POST /api/v1/middleware/process","fields":[{"name":"status","type":"string"},{"name":"evidence","type":"object"},{"name":"compact_context","type":"string"},{"name":"stages","type":"array"},{"name":"errors","type":"array"},{"name":"final_price","type":"number|null"},{"name":"audit_hash","type":"sha256"}]}]
def ok(data,status=200): return jsonify({"status":"ok","data":data}),status
def error(msg,status=400): return jsonify({"status":"error","message":msg}),status
@app.errorhandler(ValueError)
def bad(exc): return error(str(exc))
@app.get("/health")
def health(): return ok({"service":"uc284-resilient-middleware","ready":True})
@app.get("/api/v1/schema")
def schema(): return ok({"input_cards":INPUT_CARDS,"output_cards":OUTPUT_CARDS})
@app.post("/api/v1/middleware/process")
def process():
    d=request.get_json(silent=True) or {}; required=["objective","sku","current_price","proposed_price"]
    missing=[k for k in required if k not in d]
    if missing:return error(f"Missing required fields: {', '.join(missing)}")
    req=AgentRequest(str(d["objective"]),str(d["sku"]),float(d["current_price"]),float(d["proposed_price"]),d.get("facts",{}),d.get("query",""),bool(d.get("execute",False)),bool(d.get("approved",False)))
    ctx=middleware.process(req); out=ctx.public_dict(); out["audit_hash"]=ctx.audit_hash(); return ok(out)
@app.get("/api/v1/memory")
def stats(): return ok({"stats":memory.stats(),"facts":memory.facts()})
if __name__=="__main__": app.run(host="0.0.0.0",port=5284,debug=False)