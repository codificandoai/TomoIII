"""Governance, risk and accountability contracts."""
from __future__ import annotations
import time
from dataclasses import asdict,dataclass,field
from enum import Enum
from typing import Any,Dict,List,Optional
from uuid import uuid4
class RiskLevel(str,Enum): LOW="low"; MEDIUM="medium"; HIGH="high"; CRITICAL="critical"
class Outcome(str,Enum): AUTO_APPROVED="auto_approved"; APPROVAL_REQUIRED="approval_required"; APPROVED="approved"; BLOCKED_POLICY="blocked_policy"; BLOCKED_ANOMALY="blocked_anomaly"; CIRCUIT_OPEN="circuit_open"
class AccountableRole(str,Enum): DEPLOYING_ORGANIZATION="deploying_organization"; POLICY_OWNER="policy_owner"; HUMAN_APPROVER="human_approver"; OPERATIONS="operations"
@dataclass(frozen=True)
class GovernancePolicy:
    version:str="1.0"; floor_margin:float=.05; max_change_rate:float=.10; ceiling_cost_multiple:float=3.0
    max_actions_per_hour:int=50; approval_change_rate:float=.05; impact_budget:float=250000
    circuit_failure_threshold:int=3; micro_adjustment_min:float=.01; micro_adjustment_max:float=.05
@dataclass(frozen=True)
class AgentAction:
    agent_id:str; organization_id:str; tool:str; params:Dict[str,Any]; reasoning:str
    idempotency_key:str; model_version:str="unknown"; timestamp:float=field(default_factory=time.time)
    def validate(self):
        if not all([self.agent_id.strip(),self.organization_id.strip(),self.tool.strip(),self.idempotency_key.strip()]): raise ValueError("agent, organization, tool and idempotency_key are required")
@dataclass(frozen=True)
class HumanApproval:
    approver_id:str; role:str; justification:str; approved:bool; timestamp:float=field(default_factory=time.time)
@dataclass
class GovernanceDecision:
    action:AgentAction; risk:RiskLevel; outcome:Outcome; reasons:List[str]; accountable_role:AccountableRole
    policy_version:str; approval:Optional[HumanApproval]=None; decision_id:str=field(default_factory=lambda:uuid4().hex[:16]); timestamp:float=field(default_factory=time.time)
    def public_dict(self): return asdict(self)