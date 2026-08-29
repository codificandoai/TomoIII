"""Tamper-evident SQLite accountability ledger using a hash chain."""
import hashlib,json,sqlite3,threading
from models import GovernanceDecision
class AuditLedger:
    def __init__(self,path=":memory:"):
        self.conn=sqlite3.connect(path,check_same_thread=False);self.lock=threading.RLock()
        with self.conn:self.conn.execute("CREATE TABLE IF NOT EXISTS ledger(seq INTEGER PRIMARY KEY AUTOINCREMENT,decision_id TEXT UNIQUE,payload TEXT,prev_hash TEXT,record_hash TEXT)")
    def append(self,decision):
        payload=json.dumps(decision.public_dict(),sort_keys=True,default=str)
        with self.lock,self.conn:
            row=self.conn.execute("SELECT record_hash FROM ledger ORDER BY seq DESC LIMIT 1").fetchone();prev=row[0] if row else "GENESIS"
            digest=hashlib.sha256((prev+payload).encode()).hexdigest()
            self.conn.execute("INSERT INTO ledger(decision_id,payload,prev_hash,record_hash) VALUES (?,?,?,?)",(decision.decision_id,payload,prev,digest))
        return digest
    def records(self,limit=100):
        with self.lock:rows=self.conn.execute("SELECT seq,decision_id,payload,prev_hash,record_hash FROM ledger ORDER BY seq DESC LIMIT ?",(limit,)).fetchall()
        return [{"seq":r[0],"decision_id":r[1],"decision":json.loads(r[2]),"prev_hash":r[3],"record_hash":r[4]} for r in rows]
    def verify(self):
        with self.lock:rows=self.conn.execute("SELECT payload,prev_hash,record_hash FROM ledger ORDER BY seq").fetchall()
        prev="GENESIS"
        for payload,stored_prev,digest in rows:
            if stored_prev!=prev or hashlib.sha256((prev+payload).encode()).hexdigest()!=digest:return False
            prev=digest
        return True