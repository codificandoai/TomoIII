"""Deterministic autonomous-agent risk governance engine."""
from __future__ import annotations
import threading,time
from collections import defaultdict,deque
from typing import Dict,List,Optional
from ledger import AuditLedger
from models import *
class RiskGovernanceEngine:
    def __init__(self,policy=None,ledger=None,costs=None,prices=None):
        self.policy=policy or GovernancePolicy();self.ledger=ledger or AuditLedger();self.costs=costs or {};self.prices=prices or {}
        self.actions=defaultdict(deque);self.failures=defaultdict(int);self.circuit_open=set();self.cache={};self.price_history=defaultdict(list);self.lock=threading.RLock()
    def evaluate(self,action:AgentAction,approval:Optional[HumanApproval]=None):
        action.validate()
        with self.lock:
            if action.idempotency_key in self.cache:return self.cache[action.idempotency_key]
            reasons=[]
            if action.agent_id in self.circuit_open:
                return self._decision(action,RiskLevel.CRITICAL,Outcome.CIRCUIT_OPEN,["agent circuit breaker is open"],AccountableRole.OPERATIONS,approval)
            now=time.time();window=self.actions[action.agent_id]
            while window and window[0]<now-3600:window.popleft()
            if len(window)>=self.policy.max_actions_per_hour:reasons.append("hourly rate limit exceeded")
            window.append(now)
            risk=RiskLevel.LOW;outcome=Outcome.AUTO_APPROVED;role=AccountableRole.DEPLOYING_ORGANIZATION
            if action.tool=="set_price":
                sku=action.params.get("sku");price=action.params.get("price");quantity=float(action.params.get("quantity",1))
                if not sku or not isinstance(price,(int,float)) or isinstance(price,bool):reasons.append("invalid set_price parameters")
                else:
                    cost=self.costs.get(sku);current=self.prices.get(sku)
                    if cost is None or current is None:reasons.append("missing authoritative cost/current price")
                    else:
                        change=abs(price-current)/current;impact=abs(price-current)*quantity
                        if price<cost*(1+self.policy.floor_margin):reasons.append("predatory or below-floor pricing")
                        if price>cost*self.policy.ceiling_cost_multiple:reasons.append("price exceeds cost ceiling")
                        if change>self.policy.max_change_rate:reasons.append("single action change limit exceeded")
                        if impact>self.policy.impact_budget:reasons.append("impact budget exceeded")
                        diff=abs(price-current)
                        recent=self.price_history[sku][-3:]
                        if self.policy.micro_adjustment_min<=diff<=self.policy.micro_adjustment_max and len(recent)>=2:reasons.append("repeated micro-adjustment pattern")
                        if not reasons and change>self.policy.approval_change_rate:
                            risk,outcome,role=RiskLevel.HIGH,Outcome.APPROVAL_REQUIRED,AccountableRole.HUMAN_APPROVER
                        self.price_history[sku].append(price)
            if reasons:
                risk,outcome,role=RiskLevel.CRITICAL,Outcome.BLOCKED_POLICY,AccountableRole.POLICY_OWNER
                self.failures[action.agent_id]+=1
                if self.failures[action.agent_id]>=self.policy.circuit_failure_threshold:self.circuit_open.add(action.agent_id)
            elif outcome==Outcome.APPROVAL_REQUIRED and approval:
                if approval.approver_id==action.agent_id: reasons=["separation of duties violation"]
                elif not approval.justification.strip(): reasons=["approval justification required"]
                elif approval.approved: outcome=Outcome.APPROVED
                else: outcome=Outcome.BLOCKED_ANOMALY
                if reasons:outcome=Outcome.BLOCKED_POLICY;role=AccountableRole.POLICY_OWNER
            decision=self._decision(action,risk,outcome,reasons,role,approval)
            if outcome in {Outcome.AUTO_APPROVED,Outcome.APPROVED} and action.tool=="set_price":self.prices[action.params["sku"]]=float(action.params["price"]);self.failures[action.agent_id]=0
            return decision
    def _decision(self,action,risk,outcome,reasons,role,approval):
        d=GovernanceDecision(action,risk,outcome,reasons,role,self.policy.version,approval);d.ledger_hash=self.ledger.append(d);self.cache[action.idempotency_key]=d;return d
    def reset_circuit(self,agent_id,operator_id):
        if not operator_id.strip():raise ValueError("operator_id required")
        self.circuit_open.discard(agent_id);self.failures[agent_id]=0
    def status(self):return {"policy":self.policy.__dict__,"open_circuits":sorted(self.circuit_open),"ledger_valid":self.ledger.verify()}