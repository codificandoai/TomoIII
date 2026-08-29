"""Framework adapters with native capability detection and deterministic fallback."""
from __future__ import annotations

import importlib.util
import math
import time
from abc import ABC, abstractmethod
from typing import Dict

from models import AgentRequest, AgentResponse, ExecutionMode, Framework


MODULES = {
    Framework.LANGGRAPH: "langgraph",
    Framework.CREWAI: "crewai",
    Framework.MAF_AUTOGEN: "autogen_agentchat",
    Framework.GOOGLE_ADK: "google.adk",
    Framework.AWS_STRANDS: "strands",
}


class FrameworkAdapter(ABC):
    framework: Framework

    def __init__(self, mode: ExecutionMode = ExecutionMode.AUTO) -> None:
        self.mode = mode

    @property
    def available(self) -> bool:
        return importlib.util.find_spec(MODULES[self.framework]) is not None

    def invoke(self, request: AgentRequest) -> AgentResponse:
        started = time.perf_counter()
        if time.time() > request.deadline:
            raise TimeoutError(f"deadline exceeded for {self.framework.value}")
        if self.mode == ExecutionMode.NATIVE and not self.available:
            raise RuntimeError(f"{self.framework.value} SDK is not installed")
        native = self.available and self.mode != ExecutionMode.SIMULATION
        response = self.invoke_native(request) if native else self.invoke_simulated(request)
        return AgentResponse(**{**response.__dict__, "latency_ms": round((time.perf_counter() - started) * 1000, 3)})

    @abstractmethod
    def invoke_simulated(self, request: AgentRequest) -> AgentResponse:
        raise NotImplementedError

    def invoke_native(self, request: AgentRequest) -> AgentResponse:
        return self.invoke_simulated(request)

    def _response(self, request: AgentRequest, price: float, confidence: float,
                  sentiment: float, rationale: str, native: bool = False, **metrics) -> AgentResponse:
        warnings = [] if native else ["deterministic_fallback"]
        return AgentResponse(self.framework, self.__class__.__name__, native, confidence,
                             round(price, 2), sentiment, rationale, metrics, warnings)


class LangGraphAdapter(FrameworkAdapter):
    framework = Framework.LANGGRAPH

    def invoke_native(self, request: AgentRequest) -> AgentResponse:
        from langgraph.graph import END, START, StateGraph
        from typing import TypedDict
        class State(TypedDict):
            price: float
            result: float
        graph = StateGraph(State)
        graph.add_node("analyze", lambda state: {"result": state["price"] * 1.01})
        graph.add_edge(START, "analyze")
        graph.add_edge("analyze", END)
        result = graph.compile().invoke({"price": request.state["current_price"], "result": 0.0})
        return self._response(request, result["result"], .86, .1,
                              "LangGraph state graph validated market state and tool flow", True,
                              graph_nodes=1)

    def invoke_simulated(self, request: AgentRequest) -> AgentResponse:
        return self._response(request, request.state["current_price"] * 1.01, .8, .1,
                              "State-graph research and tool analysis")


class CrewAIAdapter(FrameworkAdapter):
    framework = Framework.CREWAI

    def invoke_simulated(self, request: AgentRequest) -> AgentResponse:
        s = request.state
        floor = s["unit_cost"] * 1.12
        competitive = s["competitor_price"] * 1.04
        price = max(floor, min(competitive, s["current_price"] * 1.04))
        return self._response(request, price, .84, .15,
                              "Role-based quantitative analyst and pricing strategist consensus")


class MAFAutoGenAdapter(FrameworkAdapter):
    framework = Framework.MAF_AUTOGEN

    def invoke_simulated(self, request: AgentRequest) -> AgentResponse:
        text = " ".join(request.state.get("headlines", [])).lower()
        positive = sum(word in text for word in ["growth", "demand", "expansion", "crece"])
        negative = sum(word in text for word in ["shortage", "crisis", "decline", "cae"])
        sentiment = max(-1.0, min(1.0, (positive - negative) * .25))
        return self._response(request, request.state["current_price"] * (1 + sentiment * .03),
                              .78, sentiment, "Multi-agent news debate and sentiment synthesis")


class GoogleADKAdapter(FrameworkAdapter):
    framework = Framework.GOOGLE_ADK

    def invoke_simulated(self, request: AgentRequest) -> AgentResponse:
        s = request.state
        inventory_pressure = max(-.03, min(.03, (s["demand"] - s["inventory"]) / max(s["inventory"], 1) * .03))
        return self._response(request, s["current_price"] * (1 + inventory_pressure), .8, 0,
                              "ADK session and inventory tool evaluation", inventory_pressure=inventory_pressure)


class AWSStrandsAdapter(FrameworkAdapter):
    framework = Framework.AWS_STRANDS

    def invoke_simulated(self, request: AgentRequest) -> AgentResponse:
        s = request.state
        margin_target = s["unit_cost"] / .62
        price = .5 * margin_target + .5 * s["competitor_price"]
        return self._response(request, price, .82, 0,
                              "Strands tool-first margin and competitor policy evaluation")


def build_adapters(mode: ExecutionMode) -> Dict[Framework, FrameworkAdapter]:
    adapters = [LangGraphAdapter(mode), CrewAIAdapter(mode), MAFAutoGenAdapter(mode),
                GoogleADKAdapter(mode), AWSStrandsAdapter(mode)]
    return {adapter.framework: adapter for adapter in adapters}