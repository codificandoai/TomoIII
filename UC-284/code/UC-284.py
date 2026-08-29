"""UC-284 — Resilient AI agent middleware for TrackPrice."""
import argparse,json,sys
from memory import HybridMemory
from middleware import ResilientAgentMiddleware
from models import AgentRequest

def run(db):
    middleware=ResilientAgentMiddleware(HybridMemory(db))
    request=AgentRequest("Maximize profit while preserving customer trust","SKU-001",249.99,255.0,
                         {"SKU-001_cost":150,"competitor_price":245},"pricing lessons")
    ctx=middleware.process(request); out=ctx.public_dict(); out["audit_hash"]=ctx.audit_hash()
    print(json.dumps(out,indent=2,ensure_ascii=False,default=str)); return 0
def serve(port):
    from api import app
    app.run(host="0.0.0.0",port=port,debug=False); return 0
def main(argv=None):
    p=argparse.ArgumentParser(description="Resilient agent middleware"); s=p.add_subparsers(dest="command",required=True)
    r=s.add_parser("run"); r.add_argument("--db",default=":memory:")
    v=s.add_parser("serve"); v.add_argument("--port",type=int,default=5284)
    a=p.parse_args(argv); return run(a.db) if a.command=="run" else serve(a.port)
if __name__=="__main__":sys.exit(main())