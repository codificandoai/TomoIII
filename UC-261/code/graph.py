"""Compilación del grafo LangGraph adaptativo BDI para UC-261."""
from __future__ import annotations

from typing import Any, Dict, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from adaptive_nodes import AdaptiveNodes
from bdi_nodes import BDINodes
from config import AgentConfig, AppConfig, get_config
from external_api import FlightDelayPredictor
from memory import PatternMemoryDB
from models import FlightPlanRequest, now_iso
from safety import SafetyGuard
from state import AdaptiveState
from world_simulator import WorldSimulator


def _create_checkpointer(config: AppConfig) -> BaseCheckpointSaver:
    """Crea un checkpointer LangGraph: SQLite si hay path, en memoria por defecto."""
    if config.checkpoint.path:
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
            return SqliteSaver.from_conn_string(f"sqlite:///{config.checkpoint.path}")
        except Exception as exc:  # pragma: no cover - fallback
            print(f"WARN: could not create SqliteSaver ({exc}), falling back to MemorySaver")
            return MemorySaver()
    return MemorySaver()


def build_output(state: AdaptiveState) -> Dict[str, Any]:
    """Construye el payload de salida final a partir del estado actual.

    Si hay recomendaciones pendientes de aprobación y el grafo fue interrumpido
    antes del approval_handler, refleja el estado como awaiting_approval.
    """
    itinerary = state.get("itinerary", [])
    total_cost = round(sum(i.get("cost", 0.0) for i in itinerary), 2)
    currency = state["request"].get("currency", "USD")
    status = state.get("status", "done")
    if status in ("learning", "adapting", "finalizing"):
        status = "done"
    pending_approval = [
        a for a in state.get("approval_actions", [])
        if a.get("status") == "PENDING_APPROVAL"
    ]
    if pending_approval:
        status = "awaiting_approval"

    return {
        "request_id": state["request"].get("request_id"),
        "user_id": state["request"].get("user_id", "anonymous"),
        "status": status,
        "itinerary": itinerary,
        "total_cost": total_cost,
        "currency": currency,
        "beliefs": state.get("beliefs", []),
        "desires": state.get("desires", []),
        "intentions": state.get("intentions", []),
        "experiences": state.get("experiences", []),
        "recommendations": state.get("recommendations", []),
        "auto_actions": state.get("auto_actions", []),
        "approval_actions": state.get("approval_actions", []),
        "profile": state.get("profile", {}),
        "reflections": state.get("reflections", []),
        "safety_flags": state.get("safety_flags", []),
        "missing_info": state.get("missing_info", []),
        "requires_confirmation": state.get("requires_confirmation", False),
        "retry_count": state.get("retry_count", 0),
    }


def _finalizer_node(state: AdaptiveState) -> Dict[str, Any]:
    final_output = build_output(state)
    status = final_output["status"]
    return {
        "status": status,
        "final_output": final_output,
        "logs": [{"node": "finalizer", "message": f"Final status: {status}", "timestamp": now_iso()}],
    }


def build_agent(
    config: AppConfig,
    checkpointer: Optional[BaseCheckpointSaver] = None,
) -> CompiledStateGraph:
    world = WorldSimulator(config.world)
    predictor = FlightDelayPredictor(config.predictor)
    memory = PatternMemoryDB(config.memory.path)
    safety = SafetyGuard(config.agent)

    bdi = BDINodes(world, predictor, config.agent, safety)
    adaptive = AdaptiveNodes(memory, config.agent, config.memory)

    if checkpointer is None:
        checkpointer = _create_checkpointer(config)

    workflow = StateGraph(AdaptiveState)

    # BDI base nodes
    workflow.add_node("input_validation", bdi.input_validation_node)
    workflow.add_node("book_itinerary", bdi.book_itinerary_node)
    workflow.add_node("perceive", bdi.perceive_node)
    workflow.add_node("deliberate", bdi.deliberate_node)
    workflow.add_node("intend", bdi.intend_node)
    workflow.add_node("execute", bdi.execute_node)
    workflow.add_node("review", bdi.review_node)
    workflow.add_node("bdi_learn", bdi.learn_node)

    # Adaptive nodes
    workflow.add_node("load_profile", adaptive.load_profile_node)
    workflow.add_node("generate_recommendations", adaptive.generate_recommendations_node)
    workflow.add_node("control_gate", adaptive.control_gate_node)
    workflow.add_node("execute_auto", adaptive.execute_auto_node)
    workflow.add_node("approval_handler", adaptive.approval_handler_node)
    workflow.add_node("apply_approved", adaptive.apply_approved_actions_node)
    workflow.add_node("adaptive_learn", adaptive.learn_and_update_profile_node)
    workflow.add_node("finalizer", _finalizer_node)

    workflow.set_entry_point("input_validation")

    def route_after_input(state: AdaptiveState) -> str:
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

    def route_after_execute(state: AdaptiveState) -> str:
        status = state.get("status", "")
        if status == "awaiting_confirmation":
            return "finalizer"
        return "review"

    workflow.add_conditional_edges(
        "execute",
        route_after_execute,
        {"review": "review", "finalizer": "finalizer"},
    )

    def route_after_review(state: AdaptiveState) -> str:
        status = state.get("status", "")
        if status == "deliberating":
            return "deliberate"
        if status == "adapting":
            return "bdi_learn"
        return "finalizer"

    workflow.add_conditional_edges(
        "review",
        route_after_review,
        {"deliberate": "deliberate", "bdi_learn": "bdi_learn", "finalizer": "finalizer"},
    )

    workflow.add_edge("bdi_learn", "load_profile")
    workflow.add_edge("load_profile", "generate_recommendations")
    workflow.add_edge("generate_recommendations", "control_gate")
    workflow.add_edge("control_gate", "execute_auto")
    workflow.add_edge("execute_auto", "approval_handler")

    def route_after_approval(state: AdaptiveState) -> str:
        status = state.get("status", "")
        if status == "awaiting_approval":
            return "finalizer"
        return "apply_approved"

    workflow.add_conditional_edges(
        "approval_handler",
        route_after_approval,
        {"apply_approved": "apply_approved", "finalizer": "finalizer"},
    )

    workflow.add_edge("apply_approved", "adaptive_learn")
    workflow.add_edge("adaptive_learn", "finalizer")
    workflow.add_edge("finalizer", END)

    return workflow.compile(checkpointer=checkpointer)


def _make_initial_state(request: FlightPlanRequest, config: AppConfig) -> AdaptiveState:
    return {
        "request": request.to_state(),
        "user_id": request.user_id,
        "profile": {},
        "itinerary": [],
        "recommendations": [],
        "auto_actions": [],
        "approval_actions": [],
        "approved_action_ids": request.approved_action_ids,
        "rejected_action_ids": request.rejected_action_ids,
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
        "max_retries": config.agent.max_retries,
        "safety_flags": [],
        "missing_info": [],
        "user_confirmed": request.confirm_irreversible,
        "requires_confirmation": False,
    }


def run_agent(
    request: FlightPlanRequest,
    config: AppConfig,
    recursion_limit: int = 50,
) -> AdaptiveState:
    """Ejecuta el agente en modo one-shot (sin persistencia entre procesos)."""
    agent = build_agent(config)
    initial_state = _make_initial_state(request, config)
    final_state = agent.invoke(
        initial_state,
        {
            "configurable": {"thread_id": f"oneshot-{request.request_id}"},
            "recursion_limit": recursion_limit,
        },
    )
    if final_state.get("final_output") is None:
        final_state["final_output"] = build_output(final_state)
    return final_state


def _thread_config(thread_id: str) -> Dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def run_agent_threaded(
    agent: CompiledStateGraph,
    request: FlightPlanRequest,
    thread_id: str,
    recursion_limit: int = 50,
) -> AdaptiveState:
    """Ejecuta el agente persistiendo el estado en el checkpointer asociado al thread_id."""
    initial_state = _make_initial_state(request, config=get_config())
    final_state = agent.invoke(
        initial_state,
        {**_thread_config(thread_id), "recursion_limit": recursion_limit},
    )
    if final_state.get("final_output") is None:
        final_state["final_output"] = build_output(final_state)
    final_state["final_output"]["thread_id"] = thread_id
    return final_state


def resume_agent_threaded(
    agent: CompiledStateGraph,
    thread_id: str,
    approved_action_ids: Optional[list] = None,
    rejected_action_ids: Optional[list] = None,
) -> AdaptiveState:
    """Reanuda un thread interrumpido ante un approval gate."""
    config = _thread_config(thread_id)
    snapshot = agent.get_state(config)
    if snapshot is None:
        raise ValueError(f"No checkpoint found for thread_id={thread_id}")

    updates: Dict[str, Any] = {}
    if approved_action_ids is not None:
        updates["approved_action_ids"] = approved_action_ids
    if rejected_action_ids is not None:
        updates["rejected_action_ids"] = rejected_action_ids

    if updates:
        agent.update_state(config, updates)

    final_state = agent.invoke(None, config)
    if final_state.get("final_output") is None:
        final_state["final_output"] = build_output(final_state)
    final_state["final_output"]["thread_id"] = thread_id
    return final_state
