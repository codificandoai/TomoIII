"""
UC-330 — Selector de políticas para Exploitation–Exploration Governance.

Calcula epsilon adaptativo y selecciona el modo (explotar/sandbox) y la
acción a tomar, combinando Q-learning, bandido contextual y curiosidad.
"""

from typing import List, Dict, Optional, Any, Tuple
import math
import random

from balance_ex_models import (
    BalanceExConfig, ContextSnapshot, Decision, DecisionMode, ExplorationStrategy,
)
from context_bandit import ContextualBandit
from q_learning_table import QLearningTable
from curiosity_engine import CuriosityEngine
from environment_detector import EnvironmentDetector
from exploration_budget import ExplorationBudget


class PolicySelector:
    """
    Selecciona acciones bajo un balance dinámico exploración-explotación.

    Lógica:
    1. Detectar cambio ambiental.
    2. Calcular epsilon_t según historial, presupuesto, incertidumbre y fase.
    3. Con probabilidad epsilon_t explorar; de lo contrario explotar.
    4. Seleccionar estrategia de exploración híbrida.
    """

    def __init__(
        self,
        actions: List[str],
        feature_keys: List[str],
        config: BalanceExConfig,
        bandit: ContextualBandit,
        q_table: QLearningTable,
        curiosity: CuriosityEngine,
        detector: EnvironmentDetector,
        budget: ExplorationBudget,
    ):
        self.actions = actions
        self.feature_keys = feature_keys
        self.config = config
        self.bandit = bandit
        self.q_table = q_table
        self.curiosity = curiosity
        self.detector = detector
        self.budget = budget
        self._history: List[Dict[str, Any]] = []
        self._step = 0
        self._last_epsilon = config.epsilon_initial

    def compute_epsilon(
        self,
        context: ContextSnapshot,
        steps_remaining: Optional[int] = None,
    ) -> float:
        """Calcula tasa de exploración dinámica."""
        self._step += 1
        epsilon = self.config.epsilon_initial

        # Decaimiento base
        epsilon *= (self.config.decay_rate ** self._step)

        # Ajuste por cambio detectado
        if self.detector.detect_change():
            epsilon = min(self.config.epsilon_initial, epsilon * 1.5)

        # Ajuste por fase de explotación (si hay horizonte)
        if self.config.horizon and self._step > 0.8 * self.config.horizon:
            epsilon *= 0.99

        # Ajuste por presupuesto
        epsilon = self.budget.allowed_epsilon(epsilon, steps_remaining)

        # Ajuste por incertidumbre (más incertidumbre → más exploración)
        uncertainty = self._average_uncertainty(context)
        if uncertainty > 0.5:
            epsilon = min(self.config.epsilon_initial, epsilon * (1.0 + uncertainty))

        # Ajuste por rendimiento reciente
        recent_perf = self._recent_performance()
        if recent_perf is not None:
            if recent_perf < 0.0:
                epsilon *= 1.2
            elif recent_perf > 0.5:
                epsilon *= 0.8

        # Forzar exploración si muy baja diversidad
        diversity = self._action_diversity()
        if diversity < 0.3 and epsilon < 0.15:
            epsilon = 0.15

        epsilon = max(self.config.epsilon_min, min(self.config.epsilon_initial, epsilon))
        self._last_epsilon = epsilon
        return epsilon

    def select(
        self,
        context: ContextSnapshot,
        steps_remaining: Optional[int] = None,
    ) -> Tuple[DecisionMode, ExplorationStrategy, str, float, float]:
        """
        Retorna (modo, estrategia, acción, epsilon, uncertainty).
        """
        context_vector = context.vector(self.feature_keys)
        epsilon = self.compute_epsilon(context, steps_remaining)
        uncertainty = self._average_uncertainty(context)

        u = random.random()
        if u < epsilon:
            mode = DecisionMode.SANDBOX
            strategy, action = self._select_exploration_action(context_vector)
        else:
            mode = DecisionMode.EXPLOIT
            strategy = ExplorationStrategy.RANDOM
            action = self._select_exploitation_action(context_vector)

        return mode, strategy, action, epsilon, uncertainty

    def _select_exploration_action(
        self,
        context_vector: List[float],
    ) -> Tuple[ExplorationStrategy, str]:
        """Selecciona acción de exploración con estrategia híbrida."""
        r = random.random()
        if r < 0.4:
            return ExplorationStrategy.RANDOM, random.choice(self.actions)
        elif r < 0.7:
            return ExplorationStrategy.UCB, self.bandit.select_ucb(context_vector, self.config.ucb_kappa)
        elif r < 0.9:
            return ExplorationStrategy.DIRECTED, self.bandit.select_directed(context_vector)
        else:
            # Curiosity: pick action maximizing prediction error expectation
            return ExplorationStrategy.CURIOSITY, random.choice(self.actions)

    def _select_exploitation_action(self, context_vector: List[float]) -> str:
        """Selecciona acción con mayor Q-valor o por bandido."""
        q_action = self.q_table.best_action(context_vector)
        bandit_action = self.bandit.select_ucb(context_vector, kappa=0.0)

        # Preferir acción con más trials (más confiable) si empate
        q_value = self.q_table.get(context_vector, q_action)
        bandit_mean, _ = self.bandit.predict(context_vector, bandit_action)

        if q_value >= bandit_mean:
            return q_action
        return bandit_action

    def _average_uncertainty(self, context: ContextSnapshot) -> float:
        context_vector = context.vector(self.feature_keys)
        uncertainties = []
        for action in self.actions:
            _, unc = self.bandit.predict(context_vector, action)
            uncertainties.append(unc)
        if not uncertainties:
            return 0.0
        return sum(uncertainties) / len(uncertainties)

    def _recent_performance(self, window: int = 20) -> Optional[float]:
        if len(self._history) < window:
            return None
        recent = [h["reward"] for h in self._history[-window:] if "reward" in h]
        if not recent:
            return None
        return sum(recent) / len(recent)

    def _action_diversity(self, window: int = 50) -> float:
        if len(self._history) < 2:
            return 0.0
        recent = [h["action"] for h in self._history[-window:] if "action" in h]
        if not recent:
            return 0.0
        counts = {}
        for a in recent:
            counts[a] = counts.get(a, 0) + 1
        n = len(recent)
        entropy = -sum((c / n) * math.log(max(c / n, 1e-9)) for c in counts.values())
        max_entropy = math.log(max(len(self.actions), 2))
        return entropy / max_entropy

    def record(self, action: str, reward: float, mode: DecisionMode) -> None:
        """Registra una acción ejecutada para métricas."""
        self._history.append({"action": action, "reward": reward, "mode": mode.value})

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "step": self._step,
            "last_epsilon": round(self._last_epsilon, 4),
            "history_size": len(self._history),
            "recent_performance": self._recent_performance(),
            "action_diversity": self._action_diversity(),
        }

    def reset(self) -> None:
        self._history.clear()
        self._step = 0
        self._last_epsilon = self.config.epsilon_initial
