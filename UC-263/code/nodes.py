"""Nodos LangGraph para el agente RL de recomendaciones turísticas (UC-263)."""
from __future__ import annotations

from typing import Any, Dict, List

from config import AppConfig
from environment import TourismRewardSimulator
from models import Recommendation, TrainingStats, TravelerContext, now_iso
from state import RLState
from vector_q_learner import VectorQLearner


class RLNodes:
    """Nodos del grafo de recomendación con Q-Learning vectorial."""

    def __init__(
        self,
        learner: VectorQLearner,
        simulator: TourismRewardSimulator,
        config: AppConfig,
    ) -> None:
        self.learner = learner
        self.simulator = simulator
        self.actions = config.agent.actions
        self.rng = __import__("numpy").random.default_rng(config.agent.seed)

    def _log(self, node: str, message: str) -> Dict[str, Any]:
        return {"node": node, "message": message, "timestamp": now_iso()}

    def observe_node(self, state: RLState) -> Dict[str, Any]:
        context = TravelerContext.from_dict(state["context"])
        description = context.describe()
        logs = [self._log("observe", f"Observed context: {description}")]
        return {
            "state_description": description,
            "logs": logs,
            "status": "deciding",
        }

    def decide_node(self, state: RLState) -> Dict[str, Any]:
        description = state["state_description"]
        action, exploration = self.learner.choose_action(
            description, self.actions, epsilon=state["epsilon"], rng=self.rng
        )
        q_values = self.learner.get_all_q_values(description, self.actions)
        alternatives = sorted(
            [{"action": a, "q_value": round(q, 4)} for a, q in q_values.items()],
            key=lambda x: x["q_value"],
            reverse=True,
        )
        recommendation = Recommendation(
            user_id=state["context"].get("user_id", "anonymous"),
            context=description,
            action=action,
            q_value=round(q_values.get(action, 0.0), 4),
            confidence=round(
                (q_values.get(action, 0.0) + 1) / 2.0, 4
            ),  # normalizar [-1,1] -> [0,1]
            exploration=exploration,
            alternatives=alternatives,
        )
        logs = [self._log("decide", f"Recommended {action} (exploration={exploration})")]
        return {
            "action": action,
            "q_value": q_values.get(action, 0.0),
            "recommendations": [recommendation.to_dict()],
            "logs": logs,
            "status": "rewarding",
        }

    def reward_node(self, state: RLState) -> Dict[str, Any]:
        context = TravelerContext.from_dict(state["context"])
        action = state["action"]
        reward = self.simulator.reward(context, action)
        logs = [self._log("reward", f"Reward for {action}: {reward}")]
        return {
            "reward": reward,
            "logs": logs,
            "status": "learning",
        }

    def learn_node(self, state: RLState) -> Dict[str, Any]:
        description = state["state_description"]
        action = state["action"]
        reward = state["reward"]
        # El siguiente estado es una transición simple desde el contexto actual
        next_state = f"post-{description}"
        new_q = self.learner.update(
            description,
            action,
            reward,
            next_state,
            self.actions,
        )
        logs = [
            self._log(
                "learn",
                f"Updated Q({description[:30]}..., {action}) -> {new_q:.4f}",
            )
        ]
        reflection = (
            f"Episode {state['episode']}: action={action}, reward={reward}, "
            f"new_q={new_q:.4f}, epsilon={state['epsilon']:.4f}"
        )
        return {
            "q_value": new_q,
            "logs": logs,
            "reflection": reflection,
            "status": "next",
        }

    def next_node(self, state: RLState) -> Dict[str, Any]:
        next_episode = state["episode"] + 1
        decay = self.learner.config.decay
        new_epsilon = max(0.01, state["epsilon"] * decay)
        if next_episode > state["max_episodes"]:
            return {
                "episode": next_episode,
                "epsilon": new_epsilon,
                "status": "done",
                "logs": [self._log("next", "Training finished")],
            }
        return {
            "episode": next_episode,
            "epsilon": new_epsilon,
            "status": "observing",
            "logs": [self._log("next", f"Advanced to episode {next_episode}")],
        }

    def finalize_node(self, state: RLState) -> Dict[str, Any]:
        final_q_values = self.learner.get_all_q_values(
            state["state_description"], self.actions
        )
        output = {
            "context": state["context"],
            "state_description": state["state_description"],
            "last_action": state["action"],
            "last_reward": state["reward"],
            "last_q_value": state["q_value"],
            "final_q_values": final_q_values,
            "recommendations": state.get("recommendations", []),
            "reflection": state.get("reflection", ""),
            "episode": state["episode"],
            "epsilon": state["epsilon"],
            "learner_stats": self.learner.stats(),
            "status": "done",
        }
        return {"final_output": output, "status": "done"}
