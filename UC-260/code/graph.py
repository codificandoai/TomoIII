"""Compilación del grafo BDI LangGraph para UC-260."""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from bdi_nodes import BDINodes
from config import AgentConfig, get_config
from external_api import FlightDelayPredictor
from models import FlightPlanRequest
from safety import SafetyGuard
from state import BDIState
from world_simulator import WorldSimulator


def build_agent(
    config: AgentConfig,
    world: WorldSimulator,
    predictor: FlightDelayPredictor,
) -> StateGraph:
    safety = SafetyGuard(config)
    nodes = BDINodes(world, predictor, config, safety)

    workflow = StateGraph(BDIState)

    workflow.add_node("input_validation", nodes.input_validation_node)
    workflow.add_node("book_itinerary", nodes.book_itinerary_node)
    workflow.add_node("perceive", nodes.perceive_node)
    workflow.add_node("deliberate", nodes.deliberate_node)
    workflow.add_node("intend", nodes.intend_node)
    workflow.add_node("execute", nodes.execute_node)
    workflow.add_node("review", nodes.review_node)
    workflow.add_node("learn", nodes.learn_node)
    workflow.add_node("finalizer", nodes.finalizer_node)

    workflow.set_entry_point("input_validation")

    def route_after_input(state: BDIState) -> str:
        status = state.get("status", "")
        if status == "awaiting_input":
            return "finalizer"
        if status == "awaiting_confirmation":
            return "finalizer"
        return "book_itinerary"

    workflow.add_conditional_edges(
        "input_validation",
        route_after_input,
        {"book_itinerary": "book_itinerary", "finalizer": "finalizer"},
    )

    workflow.add_edge("book_itinerary", "perceive")
    workflow.add_edge("perceive", "deliberate")
    workflow.add_edge("deliberate", "intend")
    workflow.add_edge("intend", "execute")

    def route_after_execute(state: BDIState) -> str:
        status = state.get("status", "")
        if status == "awaiting_confirmation":
            return "finalizer"
        return "review"

    workflow.add_conditional_edges(
        "execute",
        route_after_execute,
        {"review": "review", "finalizer": "finalizer"},
    )

    def route_after_review(state: BDIState) -> str:
        status = state.get("status", "")
        if status == "deliberating":
            return "deliberate"
        if status == "learning":
            return "learn"
        return "finalizer"

    workflow.add_conditional_edges(
        "review",
        route_after_review,
        {"deliberate": "deliberate", "learn": "learn", "finalizer": "finalizer"},
    )

    workflow.add_edge("learn", "finalizer")
    workflow.add_edge("finalizer", END)

    return workflow.compile()


def run_agent(
    request: FlightPlanRequest,
    config: AgentConfig,
    world: WorldSimulator,
    predictor: FlightDelayPredictor,
    recursion_limit: int = 50,
) -> BDIState:
    agent = build_agent(config, world, predictor)
    initial_state: BDIState = {
        "request": request.to_state(),
        "itinerary": [],
        "beliefs": [],
        "desires": [],
        "intentions": [],
        "experiences": [],
        "world_state": {},
        "reflections": [],
        "logs": [],
        "status": "input_validation",
        "final_output": None,
        "error_count": 0,
        "retry_count": 0,
        "max_retries": config.max_retries,
        "safety_flags": [],
        "missing_info": [],
        "user_confirmed": False,
        "requires_confirmation": False,
    }
    return agent.invoke(initial_state, {"recursion_limit": recursion_limit})
