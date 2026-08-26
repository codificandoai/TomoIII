"""Construcción y compilación del grafo LangGraph para UC-259."""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from config import AgentConfig, get_config
from models import FlightPlanRequest
from nodes import AgentNodes
from safety import SafetyGuard
from state import AgentState
from world_simulator import WorldSimulator


def build_agent(
    config: AgentConfig,
    world: WorldSimulator,
) -> StateGraph:
    """Construye el grafo ciclico del agente de viajes."""
    safety = SafetyGuard(config)
    nodes = AgentNodes(world, config, safety)

    workflow = StateGraph(AgentState)

    workflow.add_node("input_validation", nodes.input_validation_node)
    workflow.add_node("planner", nodes.planner_node)
    workflow.add_node("executor", nodes.executor_node)
    workflow.add_node("monitor_reflect", nodes.monitor_reflect_node)
    workflow.add_node("corrector", nodes.self_corrector_node)
    workflow.add_node("finalizer", nodes.finalizer_node)

    workflow.set_entry_point("input_validation")

    # Rutas condicionales
    def route_after_input(state: AgentState) -> str:
        status = state.get("status", "")
        if status in ("awaiting_input", "invalid_input"):
            return "finalizer"
        return "planner"

    workflow.add_conditional_edges(
        "input_validation",
        route_after_input,
        {"planner": "planner", "finalizer": "finalizer"},
    )

    def route_after_planner(state: AgentState) -> str:
        status = state.get("status", "")
        if status == "awaiting_input":
            return "finalizer"
        return "executor"

    workflow.add_conditional_edges(
        "planner",
        route_after_planner,
        {"executor": "executor", "finalizer": "finalizer"},
    )

    def route_after_executor(state: AgentState) -> str:
        status = state.get("status", "")
        if status == "awaiting_confirmation":
            return "finalizer"
        return "monitor_reflect"

    workflow.add_conditional_edges(
        "executor",
        route_after_executor,
        {"monitor_reflect": "monitor_reflect", "finalizer": "finalizer"},
    )

    def route_after_monitor(state: AgentState) -> str:
        status = state.get("status", "")
        if status == "correcting":
            return "corrector"
        if status == "done":
            return "finalizer"
        return "executor"

    workflow.add_conditional_edges(
        "monitor_reflect",
        route_after_monitor,
        {"corrector": "corrector", "finalizer": "finalizer", "executor": "executor"},
    )

    workflow.add_edge("corrector", "executor")
    workflow.add_edge("finalizer", END)

    return workflow.compile()


def run_agent(
    request: FlightPlanRequest,
    config: AgentConfig,
    world: WorldSimulator,
    recursion_limit: int = 50,
) -> AgentState:
    """Punto de entrada cómodo para ejecutar el agente."""
    agent = build_agent(config, world)
    initial_state: AgentState = {
        "request": request.to_state(),
        "itinerary": [],
        "status": "planning",
        "world_state": {},
        "reflections": [],
        "error_count": 0,
        "retry_count": 0,
        "max_retries": config.max_retries,
        "final_output": None,
        "safety_flags": [],
        "missing_info": [],
        "requires_confirmation": False,
        "user_confirmed": False,
        "logs": [],
    }
    return agent.invoke(initial_state, {"recursion_limit": recursion_limit})
