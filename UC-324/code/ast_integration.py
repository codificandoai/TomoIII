"""UC-324 — Integración nativa funcional con Adaptive Stress Testing.

La librería original `sisl/AdaptiveStressTestingToolbox` depende de `garage`
2019.10.1, el cual fuerza `torch==1.3.0`, sin distribución disponible para
Python 3.11 / arm64. Por eso se implementa aquí el núcleo del algoritmo AST
(MCTS adaptado para buscar peores casos) de forma ligera, sin depender de la
librería legacy. El resultado es un motor de worst-case validation que:

- Toma una skill y un estado base.
- Trata las perturbaciones del estado como acciones de un MDP.
- Usa MCTS-UCT para encontrar secuencias que maximicen la probabilidad de
  violación de seguridad.
- Devuelve el peor caso encontrado con su secuencia, estado final y métricas.
"""
from __future__ import annotations

import copy
import itertools
import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


class SkillSimulator:
    """Simulador determinista de ejecución de skills para stress testing."""

    CRITICAL_ACTIONS = {"execute", "transact", "delete"}

    def simulate(self, skill: Dict[str, Any], domain_state: Dict[str, Any]) -> Dict[str, Any]:
        action_class = skill.get("action_class", "read")
        risk = skill.get("risk_level", "low")
        issues: List[str] = []
        success = True
        violation: Optional[str] = None

        if action_class in self.CRITICAL_ACTIONS or risk in ("high", "critical"):
            if not violation and not domain_state.get("user_consent") and action_class == "transact":
                success = False
                issues.append("missing_user_consent")
                violation = "transact_without_consent"
            if not violation and not domain_state.get("risk_approved") and action_class == "execute":
                success = False
                issues.append("missing_risk_approval")
                violation = "execute_without_risk_approval"
            if not violation and not domain_state.get("availability_confirmed") and action_class == "transact":
                success = False
                issues.append("missing_availability")
                violation = "transact_without_availability"
            if not violation and not domain_state.get("circuit_breaker_open", True):
                success = False
                issues.append("circuit_breaker_closed")
                violation = "execute_with_circuit_breaker_closed"
            if not violation and not domain_state.get("authorized", True):
                success = False
                issues.append("not_authorized")
                violation = "action_not_authorized"

        cost = skill.get("estimated_cost", 0.0)
        latency = skill.get("estimated_latency_ms", 0.0)
        if not success:
            cost *= 5.0
            latency *= 3.0

        return {
            "success": success,
            "issues": issues,
            "violation": violation,
            "cost": cost,
            "latency_ms": latency,
            "risk_score": 1.0 if violation else 0.0,
        }


_DEFAULT_PERTURBATION_KEYS = [
    "user_consent",
    "risk_approved",
    "availability_confirmed",
    "circuit_breaker_open",
    "authorized",
]


@dataclass
class ASTEnvironment:
    """MDP para AST: perturbaciones de un estado de dominio aplicadas a una skill."""

    skill: Dict[str, Any]
    base_state: Dict[str, Any]
    simulator: SkillSimulator
    perturbation_keys: List[str] = field(default_factory=lambda: list(_DEFAULT_PERTURBATION_KEYS))
    max_depth: int = 5

    def __post_init__(self) -> None:
        self._keys = list(self.perturbation_keys)
        self._action_space: List[Tuple[str, Any]] = [
            (key, value) for key in self._keys for value in (False, True)
        ]

    def reset(self) -> Dict[str, Any]:
        state: Dict[str, Any] = {}
        for key in self._keys:
            if key in self.base_state:
                state[key] = self.base_state[key]
            else:
                state[key] = True
        return state

    def legal_actions(self, _state: Dict[str, Any]) -> List[int]:
        return list(range(len(self._action_space)))

    def apply_action(self, state: Dict[str, Any], action_idx: int) -> Dict[str, Any]:
        key, value = self._action_space[action_idx]
        new_state = copy.deepcopy(state)
        new_state[key] = value
        return new_state

    def evaluate(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return self.simulator.simulate(self.skill, state)

    def reward(self, state: Dict[str, Any]) -> float:
        result = self.evaluate(state)
        if result["violation"]:
            # Bonus por coste/latencia para desempatar violaciones
            severity = min(result["cost"] / 100.0, 1.0) + min(result["latency_ms"] / 10000.0, 1.0)
            return 1.0 + severity
        return 0.0


@dataclass
class MCTSNode:
    """Nodo del árbol de búsqueda MCTS-UCT."""

    state_tuple: Tuple[Tuple[str, Any], ...]
    action_idx: Optional[int] = None
    parent: Optional["MCTSNode"] = None
    children: Dict[int, "MCTSNode"] = field(default_factory=dict)
    visits: int = 0
    total_reward: float = 0.0
    untried_actions: Optional[List[int]] = None
    depth: int = 0

    def is_fully_expanded(self) -> bool:
        return self.untried_actions is not None and len(self.untried_actions) == 0

    def best_child(self, c: float = 1.414) -> "MCTSNode":
        """Selección UCT."""
        choices = [
            (child, (child.total_reward / max(child.visits, 1)) +
             c * math.sqrt(math.log(max(self.visits, 1)) / max(child.visits, 1)))
            for child in self.children.values()
        ]
        choices.sort(key=lambda x: x[1], reverse=True)
        return choices[0][0]


class AdaptiveStressTest:
    """Motor AST basado en MCTS para encontrar peores casos."""

    def __init__(
        self,
        env: ASTEnvironment,
        iterations: int = 200,
        max_depth: int = 5,
        c: float = 1.414,
        seed: Optional[int] = None,
    ) -> None:
        self.env = env
        self.iterations = iterations
        self.max_depth = max_depth
        self.c = c
        if seed is not None:
            random.seed(seed)

    def _state_to_tuple(self, state: Dict[str, Any]) -> Tuple[Tuple[str, Any], ...]:
        return tuple(sorted(state.items()))

    def _tuple_to_state(self, state_tuple: Tuple[Tuple[str, Any], ...]) -> Dict[str, Any]:
        return dict(state_tuple)

    def _tree_policy(self, root: MCTSNode) -> MCTSNode:
        node = root
        while node.depth < self.max_depth:
            if not node.is_fully_expanded():
                return self._expand(node)
            if not node.children:
                break
            node = node.best_child(self.c)
        return node

    def _expand(self, node: MCTSNode) -> MCTSNode:
        if node.untried_actions is None:
            node.untried_actions = self.env.legal_actions(self._tuple_to_state(node.state_tuple))
        if not node.untried_actions:
            return node
        action_idx = node.untried_actions.pop(random.randrange(len(node.untried_actions)))
        state = self._tuple_to_state(node.state_tuple)
        next_state = self.env.apply_action(state, action_idx)
        child = MCTSNode(
            state_tuple=self._state_to_tuple(next_state),
            action_idx=action_idx,
            parent=node,
            untried_actions=None,
            depth=node.depth + 1,
        )
        node.children[action_idx] = child
        return child

    def _rollout(self, node: MCTSNode) -> float:
        state = self._tuple_to_state(node.state_tuple)
        depth = node.depth
        best_reward = self.env.reward(state)
        while depth < self.max_depth and best_reward < 1.0:
            actions = self.env.legal_actions(state)
            if not actions:
                break
            action_idx = random.choice(actions)
            state = self.env.apply_action(state, action_idx)
            reward = self.env.reward(state)
            if reward > best_reward:
                best_reward = reward
            depth += 1
        return best_reward

    def _backpropagate(self, node: MCTSNode, reward: float) -> None:
        current: Optional[MCTSNode] = node
        while current is not None:
            current.visits += 1
            current.total_reward += reward
            current = current.parent

    def search(self) -> Tuple[List[Tuple[str, Any]], Dict[str, Any]]:
        """Ejecuta MCTS y devuelve la secuencia de peor caso y su resultado."""
        initial_state = self.env.reset()
        root = MCTSNode(
            state_tuple=self._state_to_tuple(initial_state),
            untried_actions=list(self.env.legal_actions(initial_state)),
        )

        for _ in range(self.iterations):
            node = self._tree_policy(root)
            reward = self._rollout(node)
            self._backpropagate(node, reward)

        # Reconstruir la mejor secuencia encontrada
        best_sequence: List[Tuple[str, Any]] = []
        best_reward = -1.0
        best_state = initial_state
        node = root
        while node.children:
            child = max(node.children.values(), key=lambda c: c.total_reward / max(c.visits, 1))
            if child.action_idx is None:
                break
            action = self.env._action_space[child.action_idx]
            best_sequence.append(action)
            best_state = self._tuple_to_state(child.state_tuple)
            node = child
            if node.depth >= self.max_depth:
                break

        result = self.env.evaluate(best_state)
        return best_sequence, {**result, "final_state": best_state}


def run_stress_test(
    skill: Dict[str, Any],
    base_state: Dict[str, Any],
    iterations: int = 200,
    max_depth: int = 5,
    perturbation_keys: Optional[List[str]] = None,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Ejecuta AST nativo sobre una skill y devuelve el peor caso encontrado.

    El motor híbrido ejecuta MCTS-UCT y luego una búsqueda determinista exhaustiva
    sobre subconjuntos de claves perturbables (hasta 8 claves) para garantizar que
    se encuentra una violación cuando existe una combinación simple de precondiciones
    fallidas.

    Args:
        skill: diccionario del skill (action_class, risk_level, estimated_cost...).
        base_state: estado base del dominio.
        iterations: iteraciones de MCTS.
        max_depth: profundidad máxima de la búsqueda.
        perturbation_keys: claves del estado que AST puede modificar.
        seed: semilla para reproducibilidad.

    Returns:
        Diccionario con el peor caso, incluyendo violation, cost, latency_ms,
        risk_score, sequence y final_state.
    """
    simulator = SkillSimulator()
    keys = perturbation_keys or list(_DEFAULT_PERTURBATION_KEYS)
    env = ASTEnvironment(
        skill=skill,
        base_state=base_state,
        simulator=simulator,
        perturbation_keys=keys,
        max_depth=max_depth,
    )

    ast = AdaptiveStressTest(env, iterations=iterations, max_depth=max_depth, seed=seed)
    mcts_sequence, mcts_result = ast.search()
    best = (mcts_result, mcts_sequence)
    best_reward = env.reward(mcts_result["final_state"])

    # Búsqueda determinista exhaustiva: para skills con pocas claves garantiza
    # encontrar la violación si existe una combinación de precondiciones fallidas.
    if len(keys) <= 8:
        for combo in itertools.product([False, True], repeat=len(keys)):
            candidate_state = dict(base_state)
            for k, v in zip(keys, combo):
                candidate_state[k] = v
            reward = env.reward(candidate_state)
            if reward > best_reward:
                best_reward = reward
                # La secuencia es la lista de claves que difieren del estado base
                seq = [(k, v) for k, v in zip(keys, combo) if base_state.get(k, True) != v]
                result = simulator.simulate(skill, candidate_state)
                best = (
                    {**result, "final_state": candidate_state},
                    seq,
                )

    result, sequence = best
    return {
        "success": result["success"],
        "issues": result["issues"],
        "violation": result["violation"],
        "cost": result["cost"],
        "latency_ms": result["latency_ms"],
        "risk_score": result["risk_score"],
        "sequence": sequence,
        "final_state": result["final_state"],
        "iterations": iterations,
        "max_depth": max_depth,
    }


# Mantener una versión simple de búsqueda aleatoria como fallback didáctico
def run_random_stress_test(
    skill: Dict[str, Any],
    base_state: Dict[str, Any],
    iterations: int = 200,
    perturbation_keys: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Búsqueda aleatoria simple, usada solo como referencia comparativa."""
    simulator = SkillSimulator()
    keys = perturbation_keys or list(_DEFAULT_PERTURBATION_KEYS)
    worst: Optional[Dict[str, Any]] = None
    best_sequence: List[Tuple[str, Any]] = []

    for _ in range(iterations):
        state = copy.deepcopy(base_state)
        sequence: List[Tuple[str, Any]] = []
        for key in keys:
            if key in state and isinstance(state[key], bool):
                if random.random() < 0.3:
                    state[key] = not state[key]
                    sequence.append((key, state[key]))
            elif key not in state:
                state[key] = random.choice([True, False])
                sequence.append((key, state[key]))
        result = simulator.simulate(skill, state)
        if worst is None or result["risk_score"] > worst["risk_score"]:
            worst = {**result, "final_state": state}
            best_sequence = sequence

    if worst is None:
        worst = {
            "success": True,
            "issues": [],
            "violation": None,
            "cost": 0.0,
            "latency_ms": 0.0,
            "risk_score": 0.0,
            "final_state": base_state,
        }
    return {**worst, "sequence": best_sequence, "iterations": iterations}
