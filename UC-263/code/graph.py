"""Compilación del grafo LangGraph para UC-263."""
from __future__ import annotations

from typing import Any, Dict, Optional

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from config import AppConfig, get_config
from environment import TourismRewardSimulator
from models import TravelerContext, TrainingStats
from nodes import RLNodes
from state import RLState
from vector_q_learner import VectorQLearner


def build_agent(
    config: AppConfig,
    learner: Optional[VectorQLearner] = None,
    simulator: Optional[TourismRewardSimulator] = None,
) -> CompiledStateGraph:
    learner = learner or VectorQLearner(config.rl, config.memory.path)
    simulator = simulator or TourismRewardSimulator(config.agent.actions)
    nodes = RLNodes(learner, simulator, config)

    workflow = StateGraph(RLState)

    workflow.add_node("observe", nodes.observe_node)
    workflow.add_node("decide", nodes.decide_node)
    workflow.add_node("reward", nodes.reward_node)
    workflow.add_node("learn", nodes.learn_node)
    workflow.add_node("next", nodes.next_node)
    workflow.add_node("finalize", nodes.finalize_node)

    workflow.set_entry_point("observe")
    workflow.add_edge("observe", "decide")
    workflow.add_edge("decide", "reward")
    workflow.add_edge("reward", "learn")
    workflow.add_edge("learn", "next")

    workflow.add_conditional_edges(
        "next",
        lambda state: state.get("status", ""),
        {"done": "finalize", "observing": "observe"},
    )

    workflow.add_edge("finalize", END)
    return workflow.compile()


def _initial_state(
    context: TravelerContext,
    max_episodes: int = 1,
    epsilon: Optional[float] = None,
) -> RLState:
    eps = epsilon if epsilon is not None else get_config().rl.epsilon
    return {
        "context": context.to_dict(),
        "state_description": "",
        "action": "",
        "reward": 0.0,
        "q_value": 0.0,
        "next_state_description": "",
        "episode": 1,
        "max_episodes": max(1, max_episodes),
        "epsilon": eps,
        "logs": [],
        "recommendations": [],
        "reflection": "",
        "status": "observing",
        "final_output": None,
        "error_count": 0,
    }


def recommend(
    context: TravelerContext,
    config: Optional[AppConfig] = None,
) -> Dict[str, Any]:
    """Obtiene una recomendación para un único contexto (sin entrenar)."""
    cfg = config or get_config()
    agent = build_agent(cfg)
    state = _initial_state(context, max_episodes=1, epsilon=0.0)
    final_state = agent.invoke(state, {"recursion_limit": 50})
    return final_state.get("final_output", {})


def train(
    contexts: list,
    episodes: Optional[int] = None,
    config: Optional[AppConfig] = None,
) -> Dict[str, Any]:
    """Entrena el agente con múltiples contextos a lo largo de N episodios."""
    import numpy as np

    cfg = config or get_config()
    episodes = episodes or cfg.rl.episodes
    learner = VectorQLearner(cfg.rl, cfg.memory.path)
    simulator = TourismRewardSimulator(cfg.agent.actions)

    rng = np.random.default_rng(cfg.agent.seed)
    total_reward = 0.0
    best_action_counts: Dict[str, int] = {}
    epsilon = cfg.rl.epsilon

    for episode in range(1, episodes + 1):
        context_dict = rng.choice(contexts)
        context = TravelerContext.from_dict(context_dict)
        state = _initial_state(context, max_episodes=1, epsilon=epsilon)

        # Ejecutar un episodio con el agente usando el mismo cerebro compartido
        agent = build_agent(cfg, learner=learner, simulator=simulator)
        final_state = agent.invoke(state, {"recursion_limit": 50})
        reward = final_state.get("reward", 0.0)
        action = final_state.get("action", "")
        total_reward += reward
        best_action_counts[action] = best_action_counts.get(action, 0) + 1

        epsilon = max(0.01, epsilon * cfg.rl.decay)

    stats = TrainingStats(
        episodes=episodes,
        total_reward=round(total_reward, 4),
        avg_reward=round(total_reward / max(episodes, 1), 4),
        best_action_counts=best_action_counts,
        final_epsilon=round(epsilon, 4),
    )
    return {
        "stats": stats.to_dict(),
        "learner_stats": learner.stats(),
        "status": "done",
    }
