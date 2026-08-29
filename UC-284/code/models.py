"""Contracts for the resilient agent middleware."""
from __future__ import annotations

import hashlib, json, time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

class StageStatus(str, Enum): PASS="pass"; BLOCK="block"; APPROVAL="approval_required"

@dataclass(frozen=True)
class Constitution:
    min_margin: float=.15; max_price_change: float=.10; require_grounding: bool=True
    max_steps: int=6; context_budget_chars: int=4000; approval_price_change: float=.05

@dataclass(frozen=True)
class AgentRequest:
    objective: str; sku: str; current_price: float; proposed_price: float
    facts: Dict[str, Any]=field(default_factory=dict); query: str=""; execute: bool=False; approved: bool=False
    def validate(self):
        if not self.objective.strip() or not self.sku.strip(): raise ValueError("objective and sku are required")
        if self.current_price <= 0 or self.proposed_price <= 0: raise ValueError("prices must be positive")

@dataclass(frozen=True)
class Evidence:
    key: str; value: Any; source: str; confidence: float; timestamp: float=field(default_factory=time.time)

@dataclass
class MiddlewareContext:
    request: AgentRequest; run_id: str=field(default_factory=lambda: uuid4().hex[:16])
    evidence: Dict[str, Evidence]=field(default_factory=dict); memories: List[str]=field(default_factory=list)
    compact_context: str=""; stages: List[Dict[str, Any]]=field(default_factory=list)
    final_price: Optional[float]=None; status: str="running"; errors: List[str]=field(default_factory=list)
    def record(self, stage, status, details=None): self.stages.append({"stage":stage,"status":status.value,"details":details or {},"timestamp":time.time()})
    def public_dict(self): return asdict(self)
    def audit_hash(self): return hashlib.sha256(json.dumps(self.public_dict(),sort_keys=True,default=str).encode()).hexdigest()