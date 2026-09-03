"""Compilación del grafo LangGraph para UC-292 - Multi-Agente de Trading."""
from __future__ import annotations

from typing import Optional

from langgraph.graph import END, StateGraph

from central_brain import CentralBrain
from config import AppConfig, get_config
from critic import StrategyCritic
from exchange import ExchangeSimulator
from model_persistence import ModelPersistence
from models import TradingRequest
from nodes import TradingAgentNodes
from perception import MarketPerceptionPipeline
from planner import StrategyGenerator
from risk import RiskEngine
from simulator import MonteCarloSimulator
from state import TradingAgentState
from train import load_trained_model
from world_model import TradingWorldModel


def _initial_state(request: TradingRequest, config: AppConfig) -> TradingAgentState:
    return {
        "request": request.to_dict(),
        "snapshots": None,
        "signals": [],
        "juice_validations": [],
        "bdi_state": None,
        "juice_verdict": None,
        "approved_signals": [],
        "candidates": [],
        "simulations": [],
        "evaluations": [],
        "selected_strategy": None,
        "risk_decision": None,
        "execution_result": None,
        "observations": [],
        "reflections": [],
        "logs": [],
        "status": "perceiving",
        "final_output": None,
        "error_count": 0,
        "retry_count": 0,
        "max_retries": config.agent.max_retries,
        "safety_flags": [],
        "missing_info": [],
        "requires_confirmation": False,
    }


def build_agent(
    config: Optional[AppConfig] = None,
    central_brain: Optional[CentralBrain] = None,
) -> StateGraph:
    cfg = config or get_config()
    if central_brain is None:
        world_model = TradingWorldModel(cfg.model, app_config=cfg)
        try:
            load_trained_model(world_model)
        except Exception:
            pass
        perception_pipeline = MarketPerceptionPipeline(cfg.market, cfg.features)
        central_brain = CentralBrain(
            cfg,
            world_model=world_model,
            perception_pipeline=perception_pipeline,
        )
    simulator = MonteCarloSimulator(central_brain.world_model, cfg.model)
    critic = StrategyCritic(cfg.model)
    planner = StrategyGenerator(central_brain.world_model, cfg.model)
    exchange = ExchangeSimulator()
    risk_engine = RiskEngine(constraints=cfg.risk)

    nodes = TradingAgentNodes(
        config=cfg,
        simulator=simulator,
        critic=critic,
        planner=planner,
        exchange=exchange,
        risk_engine=risk_engine,
        central_brain=central_brain,
    )

    workflow = StateGraph(TradingAgentState)

    workflow.add_node("perceive", nodes.perceive_node)
    workflow.add_node("analyze", nodes.analyze_node)
    workflow.add_node("validate", nodes.validate_node)
    workflow.add_node("plan", nodes.plan_node)
    workflow.add_node("simulate", nodes.simulate_node)
    workflow.add_node("evaluate", nodes.evaluate_node)
    workflow.add_node("adversarial_confrontation", nodes.adversarial_confrontation_node)
    workflow.add_node("risk_gate", nodes.risk_gate_node)
    workflow.add_node("confirm_or_execute", nodes.confirm_or_execute_node)
    workflow.add_node("execute", nodes.execute_node)
    workflow.add_node("learn", nodes.learn_node)
    workflow.add_node("finalize", nodes.finalize)

    workflow.set_entry_point("perceive")
    workflow.add_edge("perceive", "analyze")
    workflow.add_edge("analyze", "validate")
    workflow.add_edge("validate", "plan")
    workflow.add_edge("plan", "simulate")
    workflow.add_edge("simulate", "evaluate")
    workflow.add_edge("evaluate", "adversarial_confrontation")

    def route_after_confrontation(state: TradingAgentState) -> str:
        status = state.get("status", "")
        if status in ("blocked", "blocked_by_juice", "awaiting_input"):
            return "finalize"
        return "risk_gate"

    workflow.add_conditional_edges(
        "adversarial_confrontation",
        route_after_confrontation,
        {"risk_gate": "risk_gate", "finalize": "finalize"},
    )

    workflow.add_edge("risk_gate", "confirm_or_execute")

    def route_after_confirm(state: TradingAgentState) -> str:
        status = state.get("status", "")
        if status == "awaiting_confirmation":
            return "finalize"
        return "execute"

    workflow.add_conditional_edges(
        "confirm_or_execute",
        route_after_confirm,
        {"execute": "execute", "finalize": "finalize"},
    )

    workflow.add_edge("execute", "learn")
    workflow.add_edge("learn", "finalize")
    workflow.add_edge("finalize", END)

    return workflow.compile()


def run_agent(
    request: TradingRequest,
    config: Optional[AppConfig] = None,
    central_brain: Optional[CentralBrain] = None,
    recursion_limit: int = 50,
) -> TradingAgentState:
    cfg = config or get_config()
    agent = build_agent(cfg, central_brain=central_brain)
    state = _initial_state(request, cfg)
    final_state = agent.invoke(state, {"recursion_limit": recursion_limit})
    if final_state.get("final_output") is None:
        # Fallback si algo corta el grafo antes de finalizar
        fallback_brain = central_brain or CentralBrain(cfg)
        nodes = TradingAgentNodes(
            config=cfg,
            simulator=MonteCarloSimulator(fallback_brain.world_model, cfg.model),
            critic=StrategyCritic(cfg.model),
            planner=StrategyGenerator(fallback_brain.world_model, cfg.model),
            exchange=ExchangeSimulator(),
            risk_engine=RiskEngine(cfg.risk),
            central_brain=fallback_brain,
        )
        final_state["final_output"] = nodes.finalize(final_state)["final_output"]
    return final_state
