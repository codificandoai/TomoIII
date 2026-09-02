"""MCTS (Monte Carlo Tree Search) para estrategias de trading en UC-292."""
from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Optional

import numpy as np

from config import MCTSConfig
from mcts_store import MCTSPersistentStore
from models import AgentAction, WorldModelState
from world_model import TradingWorldModel


class MCTSNode:
    """Nodo del árbol MCTS para trading."""

    def __init__(
        self,
        state: WorldModelState,
        parent: Optional["MCTSNode"] = None,
        action: Optional[AgentAction] = None,
        is_terminal: bool = False,
        depth: int = 0,
    ) -> None:
        self.state = state
        self.parent = parent
        self.action = action
        self.children: List["MCTSNode"] = []
        self.untried_actions: List[AgentAction] = []
        self.visits = 0
        self.value = 0.0
        self.is_terminal = is_terminal
        self.depth = depth

    def fully_expanded(self) -> bool:
        return len(self.untried_actions) == 0 or self.is_terminal

    def ucb1(self, constant: float) -> float:
        if self.visits == 0:
            return float("inf")
        parent_visits = self.parent.visits if self.parent else 1
        return self.value / self.visits + constant * math.sqrt(math.log(parent_visits) / self.visits)

    def best_child(self, constant: float) -> "MCTSNode":
        return max(self.children, key=lambda c: c.ucb1(constant))


class MCTSPlanner:
    """Planificador MCTS para secuencias de órdenes de trading."""

    def __init__(self, world_model: TradingWorldModel, config: MCTSConfig) -> None:
        self.world_model = world_model
        self.config = config
        self.store = None
        if self.config.enable_persistent_tree:
            self.store = MCTSPersistentStore(self.config.persistent_tree_path)

    def search(
        self,
        initial_state: WorldModelState,
        available_actions: List[List[AgentAction]],
        rng: Optional[np.random.Generator] = None,
        request: Optional[Dict[str, Any]] = None,
    ) -> List[AgentAction]:
        rng = rng or np.random.default_rng()
        root = MCTSNode(initial_state)
        root.untried_actions = available_actions[0] if available_actions else []

        if self.store and request:
            self._seed_root(root, available_actions, request)

        for _ in range(self.config.num_iterations):
            node = self._select(root)
            if not node.fully_expanded() and not node.is_terminal:
                node = self._expand(node, available_actions)
            reward = self._simulate(node, available_actions, rng)
            self._backpropagate(node, reward)

        if self.store and request:
            self._save_root_children(root, request)

        if not root.children:
            return []
        best = max(root.children, key=lambda c: c.visits)
        plan = []
        current: Optional[MCTSNode] = best
        while current is not None and current.action is not None:
            plan.append(current.action)
            current = max(current.children, key=lambda c: c.visits) if current.children else None
        return plan

    def _seed_root(
        self,
        root: MCTSNode,
        available_actions: List[List[AgentAction]],
        request: Dict[str, Any],
    ) -> None:
        prior = self.store.get(request) if self.store else None
        if not prior or not available_actions:
            return
        action_map = {a.action_id: a for a in available_actions[0]}
        for child_data in prior:
            item_id = child_data.get("item_id")
            if item_id not in action_map:
                continue
            action = action_map[item_id]
            if action not in root.untried_actions:
                continue
            root.untried_actions.remove(action)
            transition = self.world_model.predict_transition(root.state, action)
            child_state = WorldModelState(**transition.next_state)
            child = MCTSNode(child_state, parent=root, action=action, depth=1)
            child.visits = int(child_data.get("visits", 0))
            child.value = float(child_data.get("value", 0.0))
            depth_child = 1
            child.untried_actions = (
                available_actions[depth_child].copy() if depth_child < len(available_actions) else []
            )
            if not child.untried_actions and depth_child >= len(available_actions):
                child.is_terminal = True
            root.children.append(child)

    def _save_root_children(self, root: MCTSNode, request: Dict[str, Any]) -> None:
        if not self.store:
            return
        children = [
            {
                "item_id": child.action.action_id if child.action else "",
                "visits": child.visits,
                "value": round(child.value, 4),
            }
            for child in root.children if child.action
        ]
        self.store.save(request, children)

    def _select(self, node: MCTSNode) -> MCTSNode:
        while node.fully_expanded() and node.children:
            node = node.best_child(self.config.ucb_constant)
        return node

    def _expand(self, node: MCTSNode, available_actions: List[List[AgentAction]]) -> MCTSNode:
        if node.is_terminal or not available_actions:
            return node
        depth = 0
        temp = node
        while temp.parent is not None:
            depth += 1
            temp = temp.parent
        next_actions = available_actions[depth] if depth < len(available_actions) else []
        if not next_actions:
            node.is_terminal = True
            return node
        action = next_actions.pop()
        transition = self.world_model.predict_transition(node.state, action)
        child_state = WorldModelState(**transition.next_state)
        child = MCTSNode(child_state, parent=node, action=action, depth=depth + 1)
        depth_child = depth + 1
        child.untried_actions = (
            available_actions[depth_child].copy() if depth_child < len(available_actions) else []
        )
        if not child.untried_actions and depth_child >= len(available_actions):
            child.is_terminal = True
        node.children.append(child)
        return child

    def _simulate(
        self,
        node: MCTSNode,
        available_actions: List[List[AgentAction]],
        rng: np.random.Generator,
    ) -> float:
        current_state = node.state.copy()
        total_reward = 0.0
        for level in range(node.depth, len(available_actions)):
            actions = available_actions[level]
            if not actions:
                break
            action = rng.choice(actions)
            transition = self.world_model.predict_transition(current_state, action, sample=True, rng=rng)
            total_reward += transition.reward
            current_state = WorldModelState(**transition.next_state)
        return total_reward

    def _backpropagate(self, node: MCTSNode, reward: float) -> None:
        current: Optional[MCTSNode] = node
        while current is not None:
            current.visits += 1
            current.value += reward
            current = current.parent
