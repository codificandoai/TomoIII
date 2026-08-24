"""Agente adaptativo: percepción, clasificación, planificación, ejecución y adaptación."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from config import AgentConfig
from environments.base import Environment
from models import AgentAction, AgentTrace, EnvironmentKind, Plan, SafetyCheck, StepResult, TravelRequest

from .memory import AgentMemory
from .planner import Planner
from .safety_guard import SafetyGuard
from .strategy_selector import StrategySelector

logger = logging.getLogger("uc258-agent")


class AdaptiveAgent:
    """Meta-agente que inspecciona el entorno y selecciona la política adecuada."""

    def __init__(self, name: str = "AdaptiveAgent", config: Optional[AgentConfig] = None):
        self.name = name
        self.config = config or AgentConfig()
        self.memory = AgentMemory()
        self.strategy_selector = StrategySelector()
        self.planner = Planner()
        self.safety = SafetyGuard(self.config)
        self.policy: Dict[str, Any] = {"strategy": None, "last_reward": 0.0}

    def run(
        self,
        env: Environment,
        objective: Any,
        max_iterations: Optional[int] = None,
    ) -> AgentTrace:
        """Ejecuta el ciclo completo perceive -> plan -> validate -> act -> adapt."""
        start = time.time()
        max_iterations = max_iterations or self.config.max_iterations
        trace = AgentTrace(environment_kind=getattr(env.properties, "name", "unknown"))

        # 1. Percibir y clasificar
        observation = env.get_observation()
        self.memory.store_observation(observation)
        props = env.properties
        trace.properties = props.to_dict()

        strategy = self.strategy_selector.select(props)
        trace.selected_strategy = strategy.value
        self.policy["strategy"] = strategy

        # 2. Planificar
        plan = self.planner.plan(strategy, props, objective, observation.to_dict())
        trace.plan = plan.to_dict()

        total_reward = 0.0
        iterations = 0
        last_result: Optional[StepResult] = None

        for action in plan.actions:
            if iterations >= max_iterations:
                trace.errors.append("Max iterations reached")
                break

            # 3. Validar seguridad
            safety = self.safety.check_action(action)
            trace.safety_flags.extend(safety.flags)
            if not safety.allowed:
                trace.errors.append(
                    f"Action {action.name} blocked: {safety.flags}"
                )
                action.success = False
                trace.actions.append(action.to_dict())
                continue

            # 4. Ejecutar en el entorno
            if env.is_valid_action(action):
                result = env.step(action)
            else:
                result = StepResult(
                    observation=env.get_observation(),
                    reward=-1.0,
                    done=False,
                    info={"error": "invalid_action", "action": action.name},
                )
                trace.errors.append(f"Invalid action: {action.name}")

            self.memory.store_action(action.name, result)
            action.result = result.to_dict()
            action.success = result.info.get("error") is None
            trace.actions.append(action.to_dict())
            trace.final_observation = result.observation.to_dict()
            total_reward += result.reward
            last_result = result
            iterations += 1

            if result.done:
                break

        # 5. Evaluar y adaptar
        self.policy["last_reward"] = total_reward
        trace.reward = total_reward
        trace.iterations = iterations
        trace.latency_ms = (time.time() - start) * 1000
        self._adapt(plan, trace)
        return trace

    def perceive(self, env: Environment) -> Dict[str, Any]:
        """Paso explícito de percepción."""
        obs = env.get_observation()
        self.memory.store_observation(obs)
        return obs.to_dict()

    def update_policy(self, env_change: Dict[str, Any]) -> None:
        """Actualiza la política ante cambios detectados en el entorno."""
        logger.info("Actualizando política por cambio en entorno: %s", env_change)
        self.memory.update_belief("last_env_change", env_change)

    def _adapt(self, plan: Plan, trace: AgentTrace) -> None:
        """Lógica de adaptación: si la recompensa es muy baja, bajar confianza y planificar de nuevo."""
        if trace.reward < -5:
            plan.confidence *= 0.9
            trace.safety_flags.append("adaptation: confidence reduced")
        if trace.errors:
            self.memory.update_belief("needs_clarification", True)
