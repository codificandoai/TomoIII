"""Compilación del grafo LangGraph para UC-265 - Probabilistic Model-Based Planner."""
from __future__ import annotations

from typing import Optional

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from config import AppConfig, get_config
from critic import PlanCritic
from model_persistence import ModelPersistence
from models import TravelPlanRequest
from nodes import ModelBasedNodes
from planner import PlanGenerator
from simulator import MonteCarloSimulator
from state import ModelBasedState
from train import load_trained_model
from travel_world import TravelWorldSimulator
from world_model import TravelWorldModel


def _initial_state(request: TravelPlanRequest, config: AppConfig) -> ModelBasedState:
    return {
        "request": request.to_state(),
        "world_model": {},
        "belief_state": None,
        "candidates": [],
        "simulations": [],
        "evaluations": [],
        "selected_plan": None,
        "execution_result": None,
        "observations": [],
        "reflections": [],
        "logs": [],
        "status": "building_model",
        "final_output": None,
        "error_count": 0,
        "retry_count": 0,
        "max_retries": config.agent.max_retries,
        "safety_flags": [],
        "missing_info": [],
        "requires_confirmation": False,
    }


def build_agent(config: Optional[AppConfig] = None) -> CompiledStateGraph:
    cfg = config or get_config()
    simulator_env = TravelWorldSimulator(cfg.world)
    world_model = TravelWorldModel(cfg.model, simulator_env, app_config=cfg)
    # Cargar modelos previamente entrenados si existen
    try:
        load_trained_model(world_model)
    except Exception:
        pass
    simulator = MonteCarloSimulator(world_model, cfg.model)
    critic = PlanCritic(cfg.model)
    planner = PlanGenerator(simulator_env, cfg.model)
    executor = simulator_env

    nodes = ModelBasedNodes(
        config=cfg,
        world_model=world_model,
        simulator=simulator,
        critic=critic,
        planner=planner,
        executor=executor,
    )

    workflow = StateGraph(ModelBasedState)

    workflow.add_node("parse_and_build_model", nodes.parse_and_build_model_node)
    workflow.add_node("generate_candidates", nodes.generate_candidates_node)
    workflow.add_node("simulate_candidates", nodes.simulate_candidates_node)
    workflow.add_node("evaluate_and_select", nodes.evaluate_and_select_node)
    workflow.add_node("confirm_or_execute", nodes.confirm_or_execute_node)
    workflow.add_node("execute_plan", nodes.execute_plan_node)
    workflow.add_node("learn", nodes.learn_from_observations_node)
    workflow.add_node("finalize", nodes.finalize)

    workflow.set_entry_point("parse_and_build_model")

    def route_after_parse(state: ModelBasedState) -> str:
        status = state.get("status", "")
        if status == "awaiting_input":
            return "finalize"
        return "generate_candidates"

    workflow.add_conditional_edges(
        "parse_and_build_model",
        route_after_parse,
        {"generate_candidates": "generate_candidates", "finalize": "finalize"},
    )

    workflow.add_edge("generate_candidates", "simulate_candidates")
    workflow.add_edge("simulate_candidates", "evaluate_and_select")

    def route_after_evaluate(state: ModelBasedState) -> str:
        status = state.get("status", "")
        if status == "awaiting_input":
            return "finalize"
        return "confirm_or_execute"

    workflow.add_conditional_edges(
        "evaluate_and_select",
        route_after_evaluate,
        {"confirm_or_execute": "confirm_or_execute", "finalize": "finalize"},
    )

    def route_after_confirm(state: ModelBasedState) -> str:
        status = state.get("status", "")
        if status == "awaiting_confirmation":
            return "finalize"
        return "execute_plan"

    workflow.add_conditional_edges(
        "confirm_or_execute",
        route_after_confirm,
        {"execute_plan": "execute_plan", "finalize": "finalize"},
    )

    workflow.add_edge("execute_plan", "learn")
    workflow.add_edge("learn", "finalize")
    workflow.add_edge("finalize", END)

    return workflow.compile()


def run_agent(
    request: TravelPlanRequest,
    config: Optional[AppConfig] = None,
    recursion_limit: int = 50,
) -> ModelBasedState:
    cfg = config or get_config()
    agent = build_agent(cfg)
    state = _initial_state(request, cfg)
    final_state = agent.invoke(state, {"recursion_limit": recursion_limit})
    if final_state.get("final_output") is None:
        simulator_env = TravelWorldSimulator(cfg.world)
        world_model = TravelWorldModel(cfg.model, simulator_env, app_config=cfg)
        nodes = ModelBasedNodes(
            config=cfg,
            world_model=world_model,
            simulator=MonteCarloSimulator(world_model, cfg.model),
            critic=PlanCritic(cfg.model),
            planner=PlanGenerator(simulator_env, cfg.model),
            executor=simulator_env,
        )
        final_state["final_output"] = nodes.finalize(final_state)["final_output"]
    return final_state
