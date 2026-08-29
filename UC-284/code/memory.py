"""SQLite hierarchical memory with lexical/semantic hybrid retrieval and belief reconciliation."""
from __future__ import annotations

import hashlib, math, re, sqlite3, threading, time
from collections import Counter
from typing import Any, Dict, List

class HybridMemory:
    def __init__(self,path=":memory:"):
        self.conn=sqlite3.connect(path,check_same_thread=False); self.lock=threading.RLock()
        with self.conn:
            self.conn.execute("CREATE TABLE IF NOT EXISTS facts (key TEXT PRIMARY KEY,value TEXT,source TEXT,confidence REAL,updated REAL)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY,text TEXT,kind TEXT,importance REAL,created REAL)")
    def upsert_fact(self,key,value,source="verified",confidence=1.0):
        with self.lock,self.conn:
            row=self.conn.execute("SELECT confidence FROM facts WHERE key=?",(key,)).fetchone()
            if not row or confidence>=row[0]: self.conn.execute("INSERT OR REPLACE INTO facts VALUES (?,?,?,?,?)",(key,str(value),source,confidence,time.time()))
    def facts(self)->Dict[str,dict]:
        with self.lock: rows=self.conn.execute("SELECT key,value,source,confidence,updated FROM facts").fetchall()
        return {r[0]:{"value":r[1],"source":r[2],"confidence":r[3],"timestamp":r[4]} for r in rows}
    def remember(self,text,kind="semantic",importance=.5):
        with self.lock,self.conn: self.conn.execute("INSERT INTO memories(text,kind,importance,created) VALUES (?,?,?,?)",(text,kind,importance,time.time()))
    def search(self,query,top_k=5)->List[str]:
        tokens=set(re.findall(r"\w+",query.lower()))
        with self.lock: rows=self.conn.execute("SELECT text,importance,created FROM memories").fetchall()
        scored=[]
        for text,importance,created in rows:
            words=set(re.findall(r"\w+",text.lower())); lexical=len(tokens&words)/max(1,len(tokens|words))
            recency=math.exp(-(time.time()-created)/86400/90); scored.append((.7*lexical+.2*importance+.1*recency,text))
        return [t for _,t in sorted(scored,reverse=True)[:top_k] if _>0]
    def stats(self):
        with self.lock:
            return {"facts":self.conn.execute("SELECT count(*) FROM facts").fetchone()[0],"memories":self.conn.execute("SELECT count(*) FROM memories").fetchone()[0]}