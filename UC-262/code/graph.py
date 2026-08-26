"""Compilación del grafo LangGraph para UC-262 - IA Genérica evolutiva."""
from __future__ import annotations

from typing import Any, Dict, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from cognitive_nodes import CognitiveNodes
from config import AgentConfig, AppConfig, get_config
from evolution import EvolutionEngine
from memory import LongTermMemory
from models import TravelRequest, now_iso
from safety import SafetyGuard
from state import GenericAIState
from world_simulator import WorldSimulator


def _create_checkpointer(config: AppConfig) -> BaseCheckpointSaver:
    if config.checkpoint.path:
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
            return SqliteSaver.from_conn_string(f"sqlite:///{config.checkpoint.path}")
        except Exception as exc:  # pragma: no cover
            print(f"WARN: could not create SqliteSaver ({exc}), falling back to MemorySaver")
            return MemorySaver()
    return MemorySaver()


def build_agent(
    config: AppConfig,
    checkpointer: Optional[BaseCheckpointSaver] = None,
) -> CompiledStateGraph:
    memory = LongTermMemory(config.memory.path)
    world = WorldSimulator(config.world)
    engine = EvolutionEngine(world, config.evolution)
    safety = SafetyGuard(config.agent)
    nodes = CognitiveNodes(memory, world, engine, safety, config.agent)

    if checkpointer is None:
        checkpointer = _create_checkpointer(config)

    workflow = StateGraph(GenericAIState)

    workflow.add_node("input_and_memory", nodes.input_and_memory_node)
    workflow.add_node("evolve", nodes.evolution_node)
    workflow.add_node("reason", nodes.reasoning_node)
    workflow.add_node("self_reflect", nodes.self_reflection_node)
    workflow.add_node("collaborate", nodes.collaboration_node)
    workflow.add_node("execute", nodes.execute_node)
    workflow.add_node("learn", nodes.meta_learning_node)
    workflow.add_node("finalize", nodes.finalize)

    workflow.set_entry_point("input_and_memory")

    def route_after_input(state: GenericAIState) -> str:
        status = state.get("status", "")
        if status == "awaiting_input":
            return "finalize"
        return "evolve"

    workflow.add_conditional_edges(
        "input_and_memory",
        route_after_input,
        {"evolve": "evolve", "finalize": "finalize"},
    )

    workflow.add_edge("evolve", "reason")
    workflow.add_edge("reason", "self_reflect")

    def route_after_reflection(state: GenericAIState) -> str:
        status = state.get("status", "")
        if status == "collaborating":
            return "collaborate"
        return "execute"

    workflow.add_conditional_edges(
        "self_reflect",
        route_after_reflection,
        {"collaborate": "collaborate", "execute": "execute"},
    )

    workflow.add_edge("collaborate", "execute")

    def route_after_execute(state: GenericAIState) -> str:
        status = state.get("status", "")
        if status == "awaiting_confirmation":
            return "finalize"
        return "learn"

    workflow.add_conditional_edges(
        "execute",
        route_after_execute,
        {"learn": "learn", "finalize": "finalize"},
    )

    workflow.add_edge("learn", "finalize")
    workflow.add_edge("finalize", END)

    return workflow.compile(checkpointer=checkpointer)


def _make_initial_state(request: TravelRequest, config: AppConfig) -> GenericAIState:
    return {
        "request": request.to_state(),
        "user_id": request.user_id,
        "thread_id": request.thread_id,
        "memory_context": {},
        "beliefs": [],
        "desires": [],
        "intentions": [],
        "reasoning_chain": [],
        "population": [],
        "generation": 0,
        "best_candidate": None,
        "self_critique": "",
        "human_feedback": request.human_feedback,
        "approved_alternative": request.approved_alternative,
        "final_plan": [],
        "itinerary": [],
        "reflections": [],
        "logs": [],
        "status": "memory",
        "final_output": None,
        "error_count": 0,
        "retry_count": 0,
        "max_retries": config.agent.max_retries,
        "safety_flags": [],
        "missing_info": [],
        "user_confirmed": request.confirm_irreversible,
        "requires_confirmation": False,
        "evolution_stats": {},
        "audit_trail": [],
    }


def _thread_config(thread_id: str) -> Dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def run_agent(
    request: TravelRequest,
    config: AppConfig,
    recursion_limit: int = 50,
) -> GenericAIState:
    agent = build_agent(config)
    initial_state = _make_initial_state(request, config)
    final_state = agent.invoke(
        initial_state,
        {**_thread_config(f"oneshot-{request.request_id}"), "recursion_limit": recursion_limit},
    )
    if final_state.get("final_output") is None:
        final_state["final_output"] = CognitiveNodes(
            LongTermMemory(config.memory.path),
            WorldSimulator(config.world),
            EvolutionEngine(WorldSimulator(config.world), config.evolution),
            SafetyGuard(config.agent),
            config.agent,
        ).finalize(final_state)["final_output"]
    return final_state


def run_agent_threaded(
    agent: CompiledStateGraph,
    request: TravelRequest,
    thread_id: str,
    recursion_limit: int = 50,
) -> GenericAIState:
    initial_state = _make_initial_state(request, get_config())
    final_state = agent.invoke(
        initial_state,
        {**_thread_config(thread_id), "recursion_limit": recursion_limit},
    )
    if final_state.get("final_output") is None:
        nodes = _nodes_from_config(get_config())
        final_state["final_output"] = nodes.finalize(final_state)["final_output"]
    if final_state["final_output"]:
        final_state["final_output"]["thread_id"] = thread_id
    return final_state


def resume_agent_threaded(
    agent: CompiledStateGraph,
    thread_id: str,
    human_feedback: str = "",
    approved_alternative: str = "",
) -> GenericAIState:
    config = _thread_config(thread_id)
    snapshot = agent.get_state(config)
    if snapshot is None:
        raise ValueError(f"No checkpoint found for thread_id={thread_id}")

    updates: Dict[str, Any] = {}
    if human_feedback:
        updates["human_feedback"] = human_feedback
    if approved_alternative:
        updates["approved_alternative"] = approved_alternative

    if updates:
        agent.update_state(config, updates)

    final_state = agent.invoke(None, config)
    if final_state.get("final_output") is None:
        nodes = _nodes_from_config(get_config())
        final_state["final_output"] = nodes.finalize(final_state)["final_output"]
    if final_state["final_output"]:
        final_state["final_output"]["thread_id"] = thread_id
    return final_state


def _nodes_from_config(config: AppConfig) -> CognitiveNodes:
    return CognitiveNodes(
        LongTermMemory(config.memory.path),
        WorldSimulator(config.world),
        EvolutionEngine(WorldSimulator(config.world), config.evolution),
        SafetyGuard(config.agent),
        config.agent,
    )
