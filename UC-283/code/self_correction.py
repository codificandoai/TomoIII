"""Governed LangGraph self-correction loop for pricing decisions."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, START, StateGraph

from mcp_server import MCPToolServer, build_pricing_server
from memory import LessonMemory
from models import Attempt, Critique, GateStatus, LoopResult, MarketContext, PricingPolicy


class Predictor:
    def generate(self, context: MarketContext, attempt_number: int,
                 previous: Critique | None, lessons: List[str]) -> Attempt:
        if previous is None:
            price = context.competitor_price * 1.18
            reasoning = "Initial market-value hypothesis"
        else:
            lower = max(context.cost / (1 - .15), context.competitor_price * .95,
                        context.current_price - 2 * context.historical_volatility)
            upper = min(context.cost / (1 - .60), context.competitor_price * 1.15,
                        context.current_price + 2 * context.historical_volatility)
            price = (lower + upper) / 2
            reasoning = f"Minimal correction from deterministic critic; lessons={lessons[-3:]}"
        return Attempt(attempt_number, round(price, 2), reasoning, {})


class IndependentCritic:
    def __init__(self, policy: PricingPolicy) -> None: self.policy = policy

    def evaluate(self, context: MarketContext, attempt: Attempt) -> Critique:
        p, errors, score = attempt.proposed_price, [], 100.0
        margin = (p - context.cost) / p if p else -1
        gap = (p - context.competitor_price) / context.competitor_price
        change = abs(p - context.current_price)
        checks = [
            ("margin_floor", margin >= self.policy.min_margin, 35, margin),
            ("margin_ceiling", margin <= self.policy.max_margin, 20, margin),
            ("competitive_ceiling", gap <= self.policy.max_competitor_gap, 30, gap),
            ("competitive_floor", gap >= self.policy.min_competitor_gap, 15, gap),
            ("volatility", change <= context.historical_volatility * self.policy.max_volatility_multiple, 25, change),
            ("finite_positive", p > 0, 100, p),
        ]
        challenge_results = []
        for name, passed, penalty, value in checks:
            challenge_results.append({"gate": name, "passed": passed, "value": round(value, 6)})
            if not passed:
                errors.append(name); score -= penalty
        score = max(0.0, score)
        status = GateStatus.PASS if score >= self.policy.approval_threshold and not errors else GateStatus.FAIL
        return Critique(score, status, errors, {"margin": margin, "competitor_gap": gap, "price_change": change}, challenge_results)


class LoopState(TypedDict, total=False):
    context: MarketContext
    attempts: List[Attempt]
    max_attempts: int
    lessons: List[str]
    done: bool


class GovernedPricingLoop:
    def __init__(self, memory: LessonMemory | None = None,
                 policy: PricingPolicy | None = None, max_attempts: int = 4) -> None:
        self.memory, self.policy, self.max_attempts = memory or LessonMemory(), policy or PricingPolicy(), max_attempts
        self.predictor, self.critic = Predictor(), IndependentCritic(self.policy)
        self.server: MCPToolServer | None = None
        graph = StateGraph(LoopState)
        graph.add_node("observe", self._observe)
        graph.add_node("analyze_fix", self._analyze_fix)
        graph.add_node("verify_challenge", self._verify)
        graph.add_node("learn", self._learn)
        graph.add_edge(START, "observe"); graph.add_edge("observe", "analyze_fix")
        graph.add_edge("analyze_fix", "verify_challenge"); graph.add_edge("verify_challenge", "learn")
        graph.add_conditional_edges("learn", lambda s: "done" if s["done"] else "retry",
                                    {"done": END, "retry": "analyze_fix"})
        self.graph = graph.compile()

    def execute(self, context: MarketContext, apply: bool = False,
                approved: bool = False) -> LoopResult:
        context.validate()
        self.server = build_pricing_server(lambda: asdict(context))
        lessons = self.memory.recall(context.product_id)
        state = self.graph.invoke({"context": context, "attempts": [], "max_attempts": self.max_attempts,
                                   "lessons": lessons, "done": False})
        attempts = state["attempts"]
        final = attempts[-1].proposed_price if attempts and attempts[-1].critique.status == GateStatus.PASS else None
        status = "approved" if final is not None else "failed"
        if apply and final is not None:
            tool = self.server.call_tool("apply_price", {"price": final}, approved=approved)
            status = "applied" if tool["status"] == "ok" else "approval_required"
        return LoopResult(context, attempts, final, status, self.memory.recall(context.product_id))

    def _observe(self, state: LoopState) -> dict:
        evidence = self.server.call_tool("get_market_context", {"product_id": state["context"].product_id})
        return {"lessons": state["lessons"] + [f"observed:{evidence['status']}"]}

    def _analyze_fix(self, state: LoopState) -> dict:
        previous = state["attempts"][-1].critique if state["attempts"] else None
        attempt = self.predictor.generate(state["context"], len(state["attempts"]) + 1, previous, state["lessons"])
        attempt.evidence = self.server.call_tool("run_pricing_challenge", {"price": attempt.proposed_price})
        return {"attempts": state["attempts"] + [attempt]}

    def _verify(self, state: LoopState) -> dict:
        attempt = state["attempts"][-1]
        attempt.critique = self.critic.evaluate(state["context"], attempt)
        return {"attempts": state["attempts"]}

    def _learn(self, state: LoopState) -> dict:
        attempt = state["attempts"][-1]
        if attempt.critique.errors:
            for category in attempt.critique.errors:
                lesson = f"Avoid {category}; use deterministic feasible interval"
                self.memory.learn(state["context"].product_id, category, lesson,
                                  attempt.proposed_price, state["context"].current_price)
        done = attempt.critique.status == GateStatus.PASS or len(state["attempts"]) >= state["max_attempts"]
        return {"done": done, "lessons": self.memory.recall(state["context"].product_id)}