"""UC-289 — Autonomous agent risk governance and accountability."""
import argparse,json,sys
from governance import RiskGovernanceEngine
from ledger import AuditLedger
from models import AgentAction

def run(db):
 e=RiskGovernanceEngine(ledger=AuditLedger(db),costs={"SKU-001":100},prices={"SKU-001":150})
 actions=[AgentAction("pricing-agent","trackprice","set_price",{"sku":"SKU-001","price":154,"quantity":1000},"optimize margin","demo-1","v1"),AgentAction("pricing-agent","trackprice","set_price",{"sku":"SKU-001","price":95,"quantity":1000},"exploit apparent opportunity","demo-2","v1")]
 out=[]
 for a in actions:
  d=e.evaluate(a);x=d.public_dict();x["ledger_hash"]=d.ledger_hash;out.append(x)
 print(json.dumps({"decisions":out,"status":e.status()},indent=2,ensure_ascii=False,default=str));return 0
def serve(port):
 from api import app
 app.run(host="0.0.0.0",port=port,debug=False);return 0
def main(argv=None):
 p=argparse.ArgumentParser();s=p.add_subparsers(dest="cmd",required=True);r=s.add_parser("run");r.add_argument("--db",default=":memory:");v=s.add_parser("serve");v.add_argument("--port",type=int,default=5289);a=p.parse_args(argv);return run(a.db) if a.cmd=="run" else serve(a.port)
if __name__=="__main__":sys.exit(main())