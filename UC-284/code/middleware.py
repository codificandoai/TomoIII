"""Composable reliability middleware for grounded, aligned agent actions."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import List

from memory import HybridMemory
from models import Constitution, Evidence, MiddlewareContext, StageStatus

class Stage(ABC):
    name="stage"
    @abstractmethod
    def invoke(self,ctx:MiddlewareContext,memory:HybridMemory,policy:Constitution)->StageStatus: ...

class RetrievalStage(Stage):
    name="memory_retrieval"
    def invoke(self,ctx,memory,policy):
        ctx.memories=memory.search(ctx.request.query or ctx.request.objective,5)
        for key,item in memory.facts().items(): ctx.evidence[key]=Evidence(key,item["value"],item["source"],item["confidence"],item["timestamp"])
        return StageStatus.PASS

class GroundingStage(Stage):
    name="grounding"
    def invoke(self,ctx,memory,policy):
        for key,value in ctx.request.facts.items():
            memory.upsert_fact(key,value,"request",.95); ctx.evidence[key]=Evidence(key,value,"request",.95)
        required={f"{ctx.request.sku}_cost","competitor_price"}
        missing=sorted(required-set(ctx.evidence))
        if policy.require_grounding and missing: ctx.errors.append(f"missing grounded facts: {missing}"); return StageStatus.BLOCK
        return StageStatus.PASS

class ContextStage(Stage):
    name="context_compaction"
    def invoke(self,ctx,memory,policy):
        payload={"objective":ctx.request.objective,"sku":ctx.request.sku,
                 "verified_facts":{k:{"value":e.value,"source":e.source,"confidence":e.confidence} for k,e in ctx.evidence.items()},
                 "relevant_memories":ctx.memories[:5]}
        text=json.dumps(payload,ensure_ascii=False,sort_keys=True)
        ctx.compact_context=text[:policy.context_budget_chars]
        return StageStatus.PASS

class AlignmentStage(Stage):
    name="constitutional_alignment"
    def invoke(self,ctx,memory,policy):
        cost=float(ctx.evidence[f"{ctx.request.sku}_cost"].value)
        proposed=ctx.request.proposed_price
        if proposed<cost/(1-policy.min_margin): ctx.errors.append("minimum margin violated"); return StageStatus.BLOCK
        change=abs(proposed-ctx.request.current_price)/ctx.request.current_price
        if change>policy.max_price_change: ctx.errors.append("maximum price change violated"); return StageStatus.BLOCK
        if ctx.request.execute and change>policy.approval_price_change and not ctx.request.approved: return StageStatus.APPROVAL
        return StageStatus.PASS

class VerificationStage(Stage):
    name="deterministic_verification"
    def invoke(self,ctx,memory,policy):
        competitor=float(ctx.evidence["competitor_price"].value)
        if ctx.request.proposed_price>competitor*1.2: ctx.errors.append("competitive ceiling violated"); return StageStatus.BLOCK
        ctx.final_price=ctx.request.proposed_price
        return StageStatus.PASS

class LearningStage(Stage):
    name="continual_alignment"
    def invoke(self,ctx,memory,policy):
        if ctx.errors: memory.remember(f"{ctx.request.sku}: {'; '.join(ctx.errors)}","lesson",.9)
        else: memory.remember(f"{ctx.request.sku}: aligned price {ctx.final_price}","episode",.6)
        return StageStatus.PASS

class ResilientAgentMiddleware:
    def __init__(self,memory=None,constitution=None,stages=None):
        self.memory=memory or HybridMemory(); self.constitution=constitution or Constitution()
        self.stages=stages or [RetrievalStage(),GroundingStage(),ContextStage(),AlignmentStage(),VerificationStage(),LearningStage()]
    def process(self,request):
        request.validate(); ctx=MiddlewareContext(request)
        for index,stage in enumerate(self.stages):
            if index>=self.constitution.max_steps: ctx.errors.append("complexity budget exhausted"); ctx.status="blocked"; break
            status=stage.invoke(ctx,self.memory,self.constitution); ctx.record(stage.name,status)
            if status==StageStatus.BLOCK:
                ctx.status="blocked"
                LearningStage().invoke(ctx,self.memory,self.constitution)
                break
            if status==StageStatus.APPROVAL: ctx.status="approval_required"; break
        else: ctx.status="executed" if request.execute else "validated"
        return ctx