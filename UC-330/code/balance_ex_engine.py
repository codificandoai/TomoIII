"""
UC-330 — Motor Balance-EX para Exploitation–Exploration Governance.

Coordina la detección de contexto, selección de acción, control de
seguridad, aprendizaje, presupuesto y métricas.
"""

import time
import statistics
from typing import List, Dict, Optional, Any

from balance_ex_models import (
    BalanceExConfig, BalanceExResult, BalanceMetrics, ContextSnapshot,
    ActionRecord, Decision, DecisionMode, ExplorationStrategy,
)
from context_bandit import ContextualBandit
from q_learning_table import QLearningTable
from curiosity_engine import CuriosityEngine
from environment_detector import EnvironmentDetector
from exploration_budget import ExplorationBudget
from policy_selector import PolicySelector
from safety_governor import SafetyGovernor


class BalanceExEngine:
    """
    Motor principal de UC-330 Balance-EX.

    Expone:
    - `decide(context, environment='sandbox', authorized_actions=...)`
    - `update(action, context, reward, next_context, ...)`
    - `recommend()`

    Garantiza que la exploración no ocurra en producción sin autorización.
    """

    def __init__(
        self,
        actions: List[str],
        feature_keys: List[str],
        config: Optional[BalanceExConfig] = None,
    ):
        self.actions = actions
        self.feature_keys = feature_keys
        self.config = config or BalanceExConfig()
        self.feature_dim = len(feature_keys)

        self.detector = EnvironmentDetector(
            change_window=self.config.change_window,
            change_threshold=self.config.change_threshold,
        )
        self.bandit = ContextualBandit(
            actions=actions,
            feature_dim=self.feature_dim,
            alpha=self.config.alpha_learning,
        )
        self.q_table = QLearningTable(
            actions=actions,
            optimistic_value=0.0,
            alpha=self.config.alpha_learning,
            gamma=self.config.gamma_discount,
        )
        self.curiosity = CuriosityEngine(
            actions=actions,
            feature_dim=self.feature_dim,
            eta=self.config.info_bonus,
        )
        self.budget = ExplorationBudget(
            total_budget=self.config.exploration_budget,
            window_seconds=self.config.horizon,
        )
        self.selector = PolicySelector(
            actions=actions,
            feature_keys=feature_keys,
            config=self.config,
            bandit=self.bandit,
            q_table=self.q_table,
            curiosity=self.curiosity,
            detector=self.detector,
            budget=self.budget,
        )
        self.governor = SafetyGovernor()
        self._records: List[ActionRecord] = []

    def decide(
        self,
        context: ContextSnapshot,
        environment: str = "sandbox",
        authorized_actions: Optional[List[str]] = None,
        risk_score: float = 0.0,
        steps_remaining: Optional[int] = None,
    ) -> Decision:
        """
        Decide el modo y la acción para el contexto actual.

        Args:
            context: ContextSnapshot con features.
            environment: 'production' o 'sandbox'.
            authorized_actions: acciones permitidas en producción.
            risk_score: score de riesgo del contexto (0-1).
            steps_remaining: pasos restantes para ajuste de presupuesto.

        Returns:
            Decisión final con modo, acción, epsilon, justificación.
        """
        start = time.time()
        self.budget.reset_window()

        mode, strategy, action, epsilon, uncertainty = self.selector.select(
            context=context,
            steps_remaining=steps_remaining,
        )

        # Safety governor ajusta modo según entorno y riesgo
        final_mode = self.governor.evaluate(
            mode=mode,
            action=action,
            risk_score=risk_score,
            authorized_actions=authorized_actions,
            environment=environment,
        )

        # Si se bloquea exploración en producción, elegir acción explotadora autorizada
        if final_mode != mode and final_mode == DecisionMode.EXPLOIT:
            action = self._safe_exploit_action(context, authorized_actions)
            strategy = ExplorationStrategy.RANDOM

        justification = (
            f"epsilon={epsilon:.4f}, uncertainty={uncertainty:.4f}, "
            f"risk={risk_score:.4f}, strategy={strategy.value}. "
        )
        if final_mode == DecisionMode.SANDBOX:
            justification += "Explorar en sandbox."
        elif final_mode == DecisionMode.EXPLOIT:
            justification += "Explotar acción probada."
        else:
            justification += "Escalar por riesgo/ambigüedad."

        duration = (time.time() - start) * 1000
        decision = Decision(
            mode=final_mode,
            strategy=strategy,
            action=action,
            epsilon=epsilon,
            uncertainty=uncertainty,
            risk_score=risk_score,
            justification=justification,
            metadata={"environment": environment, "duration_ms": duration},
        )
        return decision

    def update(
        self,
        decision: Decision,
        context: ContextSnapshot,
        reward: float,
        next_context: Optional[ContextSnapshot] = None,
        cost: float = 0.0,
        duration_ms: float = 0.0,
    ) -> ActionRecord:
        """
        Registra el resultado de una acción y actualiza los modelos.

        Returns:
            ActionRecord registrado.
        """
        context_vector = context.vector(self.feature_keys)
        next_vector = next_context.vector(self.feature_keys) if next_context else None

        # Curiosity bonus
        bonus = 0.0
        if next_vector is not None:
            bonus = self.curiosity.compute_bonus(context_vector, decision.action, next_vector)
            self.curiosity.update(context_vector, decision.action, next_vector)

        adjusted_reward = reward
        if decision.mode == DecisionMode.SANDBOX:
            adjusted_reward += bonus * self.config.info_bonus
        else:
            adjusted_reward *= (1.0 - 0.05 * (1.0 - decision.epsilon))

        # Update models
        self.bandit.update(context_vector, decision.action, adjusted_reward)
        self.q_table.update(context_vector, decision.action, adjusted_reward, next_vector)

        # Register reward for change detection
        self.detector.add_reward(reward)
        self.selector.record(decision.action, reward, decision.mode)

        # Budget consumption
        if decision.mode == DecisionMode.SANDBOX:
            self.budget.consume(cost, domain=context.domain)

        record = ActionRecord(
            action=decision.action,
            context_id=context.context_id,
            mode=decision.mode,
            strategy=decision.strategy,
            reward=adjusted_reward,
            risk=decision.risk_score,
            cost=cost,
            duration_ms=duration_ms,
            metadata={"raw_reward": reward, "curiosity_bonus": bonus},
        )
        self._records.append(record)
        return record

    def recommend(self) -> List[str]:
        """Genera recomendaciones basadas en métricas actuales."""
        recs = []
        metrics = self.compute_metrics()
        if metrics.exploration_rate < 0.05 and metrics.success_rate < 0.7:
            recs.append("Aumentar exploración: la tasa es baja y el éxito no es óptimo.")
        if metrics.exploration_rate > 0.3 and metrics.success_rate < 0.6:
            recs.append("Reducir exploración: la explotación es ineficiente.")
        if metrics.change_detected:
            recs.append("Cambio ambiental detectado: mantener exploración elevada.")
        if metrics.diversity < 0.3:
            recs.append("Diversidad de acciones baja: forzar más variedad.")
        if not recs:
            recs.append("Balance actual adecuado.")
        return recs

    def compute_metrics(self) -> BalanceMetrics:
        """Calcula métricas de balance exploración-explotación."""
        m = BalanceMetrics()
        m.total_steps = len(self._records)
        m.exploit_steps = sum(1 for r in self._records if r.mode == DecisionMode.EXPLOIT)
        m.sandbox_steps = sum(1 for r in self._records if r.mode == DecisionMode.SANDBOX)
        m.escalate_steps = sum(1 for r in self._records if r.mode == DecisionMode.ESCALATE)
        m.exploration_rate = m.sandbox_steps / max(1, m.total_steps)

        if self._records:
            rewards = [r.reward for r in self._records]
            m.cumulative_reward = sum(rewards)
            m.avg_reward = m.cumulative_reward / len(rewards)
            m.success_rate = sum(1 for r in rewards if r > 0) / len(rewards)
            m.diversity = self.selector._action_diversity()
            m.regret = self._compute_regret()

        m.change_detected = self.detector.detect_change()
        m.budget_remaining = self.budget.remaining()
        return m

    def _compute_regret(self) -> float:
        if not self._records:
            return 0.0
        best_mean = max(
            (statistics.mean([r.reward for r in self._records if r.action == a]) if any(r.action == a for r in self._records) else 0.0)
            for a in self.actions
        )
        return sum(best_mean - r.reward for r in self._records)

    def _safe_exploit_action(
        self,
        context: ContextSnapshot,
        authorized_actions: Optional[List[str]],
    ) -> str:
        """Elige acción explotadora segura para producción."""
        context_vector = context.vector(self.feature_keys)
        candidates = authorized_actions or self.actions
        if not candidates:
            return self.actions[0]
        # pick authorized action with highest Q value
        best = candidates[0]
        best_q = self.q_table.get(context_vector, best)
        for a in candidates[1:]:
            q = self.q_table.get(context_vector, a)
            if q > best_q:
                best_q = q
                best = a
        return best

    def run_episode(
        self,
        contexts: List[ContextSnapshot],
        rewards: List[float],
        environment: str = "sandbox",
        authorized_actions: Optional[List[str]] = None,
    ) -> BalanceExResult:
        """Ejecuta un episodio de decisiones/actualizaciones secuenciales."""
        start = time.time()
        for i, ctx in enumerate(contexts):
            steps_remaining = len(contexts) - i - 1
            decision = self.decide(
                ctx,
                environment=environment,
                authorized_actions=authorized_actions,
                steps_remaining=steps_remaining,
            )
            next_ctx = contexts[i + 1] if i + 1 < len(contexts) else None
            self.update(
                decision=decision,
                context=ctx,
                reward=rewards[i],
                next_context=next_ctx,
            )
        duration = (time.time() - start) * 1000
        return BalanceExResult(
            decision=self._records[-1].to_dict() if self._records else None,
            metrics=self.compute_metrics(),
            history=list(self._records),
            recommendations=self.recommend(),
            duration_ms=duration,
        )

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "actions": self.actions,
            "feature_keys": self.feature_keys,
            "config": self.config.to_dict(),
            "metrics": self.compute_metrics().to_dict(),
            "selector": self.selector.get_statistics(),
            "detector": self.detector.get_statistics(),
            "budget": self.budget.get_statistics(),
            "curiosity": self.curiosity.get_statistics(),
            "governor": self.governor.get_statistics(),
            "total_records": len(self._records),
        }

    def reset(self) -> None:
        self.detector.reset()
        self.bandit.reset()
        self.q_table.reset()
        self.curiosity.reset()
        self.budget.reset()
        self.selector.reset()
        self.governor.reset()
        self._records.clear()
