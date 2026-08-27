"""MCTS (Monte Carlo Tree Search) sobre el espacio de acciones de viajes."""
from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Optional

import numpy as np

from config import MCTSConfig
from models import PlanAction, WorldModelState
from world_model import TravelWorldModel


class MCTSNode:
    """Nodo del árbol MCTS."""

    def __init__(
        self,
        state: WorldModelState,
        parent: Optional["MCTSNode"] = None,
        action: Optional[PlanAction] = None,
        is_terminal: bool = False,
        depth: int = 0,
    ) -> None:
        self.state = state
        self.parent = parent
        self.action = action
        self.children: List["MCTSNode"] = []
        self.untried_actions: List[PlanAction] = []
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
    """Planificador MCTS para secuencias de vuelo-hotel-actividad."""

    def __init__(
        self,
        world_model: TravelWorldModel,
        config: MCTSConfig,
    ) -> None:
        self.world_model = world_model
        self.config = config

    def search(
        self,
        initial_state: WorldModelState,
        available_actions: List[List[PlanAction]],
        rng: Optional[np.random.Generator] = None,
    ) -> List[PlanAction]:
        """Ejecuta MCTS y devuelve la mejor secuencia de acciones (raíz -> mejor hijo).

        `available_actions` es una lista por nivel: vuelos ida, hoteles, vuelos vuelta, etc.
        """
        rng = rng or np.random.default_rng()
        root = MCTSNode(initial_state)
        root.untried_actions = available_actions[0] if available_actions else []

        for _ in range(self.config.num_iterations):
            node = self._select(root)
            if not node.fully_expanded() and not node.is_terminal:
                node = self._expand(node, available_actions)
            reward = self._simulate(node, available_actions, rng)
            self._backpropagate(node, reward)

        if not root.children:
            return []
        # Elegir hijo más visitado
        best = max(root.children, key=lambda c: c.visits)
        plan = []
        current: Optional[MCTSNode] = best
        while current is not None and current.action is not None:
            plan.append(current.action)
            current = max(current.children, key=lambda c: c.visits) if current.children else None
        return plan

    def _select(self, node: MCTSNode) -> MCTSNode:
        while node.fully_expanded() and node.children:
            node = node.best_child(self.config.ucb_constant)
        return node

    def _expand(
        self, node: MCTSNode, available_actions: List[List[PlanAction]]
    ) -> MCTSNode:
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
        available_actions: List[List[PlanAction]],
        rng: np.random.Generator,
    ) -> float:
        current_state = node.state.copy()
        total_reward = 0.0
        # Continuar desde el nivel actual del nodo hasta el final del horizonte
        for level in range(node.depth, len(available_actions)):
            actions = available_actions[level]
            if not actions:
                break
            action = rng.choice(actions)
            transition = self.world_model.predict_transition(
                current_state, action, sample=True, rng=rng
            )
            total_reward += transition.reward
            current_state = WorldModelState(**transition.next_state)
        return total_reward

    def _backpropagate(self, node: MCTSNode, reward: float) -> None:
        current: Optional[MCTSNode] = node
        while current is not None:
            current.visits += 1
            current.value += reward
            current = current.parent
