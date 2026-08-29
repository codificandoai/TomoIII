"""Closed-loop TrackPrice orchestrator synchronizing five agent frameworks."""
from __future__ import annotations

import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List
from uuid import uuid4

from adapters import build_adapters
from models import AgentRequest, AgentResponse, ConsensusDecision, ExecutionMode, Framework, MarketState, PipelineRun
from synchronization import EventBus, IdempotencyCache


class TrackPriceFederatedOrchestrator:
    def __init__(self, state: MarketState, mode: ExecutionMode = ExecutionMode.AUTO,
                 assimilation_rate: float = .3, timeout_seconds: float = 10.0,
                 max_workers: int = 5) -> None:
        state.validate()
        if not 0 <= assimilation_rate <= 1:
            raise ValueError("assimilation_rate must be between 0 and 1")
        self.state, self.mode = state, mode
        self.assimilation_rate, self.timeout_seconds = assimilation_rate, timeout_seconds
        self.adapters = build_adapters(mode)
        self.bus, self.cache, self.runs = EventBus(), IdempotencyCache(), []
        self.max_workers = max_workers

    def run(self, task: str = "Optimize TrackPrice price", execute: bool = False,
            idempotency_key: str | None = None) -> PipelineRun:
        if not task.strip():
            raise ValueError("task is required")
        key = idempotency_key or uuid4().hex
        cached = self.cache.get(key)
        if cached:
            return cached
        run_id, correlation_id = uuid4().hex[:16], uuid4().hex[:12]
        before, deadline = self.state.public_dict(), time.time() + self.timeout_seconds
        self.bus.publish("run.started", run_id, {"frameworks": [f.value for f in self.adapters]})
        responses, failures = [], []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {}
            for framework, adapter in self.adapters.items():
                request = AgentRequest(run_id, correlation_id, framework, task, before, {},
                                       f"{key}:{framework.value}", deadline)
                futures[pool.submit(adapter.invoke, request)] = framework
            for future in as_completed(futures, timeout=self.timeout_seconds + 1):
                framework = futures[future]
                try:
                    response = future.result()
                    responses.append(response)
                    self.bus.publish("framework.completed", run_id, {
                        "framework": framework.value, "native": response.native,
                        "proposed_price": response.proposed_price})
                except Exception as exc:
                    failures.append(framework.value)
                    self.bus.publish("framework.failed", run_id, {"framework": framework.value, "error": str(exc)})
        if len(responses) < 3:
            raise RuntimeError("quorum not reached: at least 3 framework responses required")
        decision = self._consensus(responses, execute, failures)
        if execute and decision.action == "execute":
            self.state.current_price = decision.applied_price
            self.state.demand = max(0, self.state.demand * (self.state.current_price / before["current_price"]) ** self.state.elasticity)
            self.state.step += 1
            self.state.version += 1
        run = PipelineRun(before, sorted(responses, key=lambda r: r.framework.value), decision,
                          self.state.public_dict(), run_id=run_id)
        self.runs.append(run)
        self.cache.put(key, run)
        self.bus.publish("run.completed", run_id, {"action": decision.action, "audit_hash": run.audit_hash()})
        return run

    def _consensus(self, responses: List[AgentResponse], execute: bool,
                   failures: List[str]) -> ConsensusDecision:
        weights = [max(.01, response.confidence) for response in responses]
        prices = [response.proposed_price for response in responses]
        recommended = sum(p * w for p, w in zip(prices, weights)) / sum(weights)
        median = statistics.median(prices)
        dispersion = statistics.pstdev(prices) / median if median else 1.0
        confidence = statistics.mean(weights) * max(0.0, 1 - min(1.0, dispersion * 3))
        floor = self.state.unit_cost * 1.1
        ceiling = self.state.competitor_price * 1.2
        max_delta = self.state.current_price * .1
        safe = min(ceiling, self.state.current_price + max_delta,
                   max(floor, self.state.current_price - max_delta, recommended))
        guardrails = []
        if dispersion > .08:
            guardrails.append("high_framework_disagreement")
        if failures:
            guardrails.append("partial_framework_failure")
        if safe != recommended:
            guardrails.append("price_clamped")
        if confidence < .6:
            guardrails.append("low_consensus_confidence")
        action = "execute" if execute and not {"high_framework_disagreement", "low_consensus_confidence"}.intersection(guardrails) else "review" if guardrails else "recommend"
        applied = self.state.current_price + (safe - self.state.current_price) * self.assimilation_rate if action == "execute" else self.state.current_price
        return ConsensusDecision(round(recommended, 2), round(applied, 2), round(confidence, 4),
                                 round(dispersion, 6), action, guardrails,
                                 {r.framework.value: r.proposed_price for r in responses})

    def status(self) -> dict:
        return {"state": self.state.public_dict(), "mode": self.mode.value,
                "frameworks": {f.value: {"available": a.available} for f, a in self.adapters.items()},
                "runs": len(self.runs)}