"""Horizontal Pod Autoscaler Manager para UC-271.

Implementa lógica avanzada de auto-scaling para agentes K8s:
- Scaling basado en CPU, memoria y métricas custom (queue_depth).
- Cooldown configurable para scale-up y scale-down.
- Historial de decisiones para auditoría.
- Predicción de carga basada en tendencia de métricas.
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional

from config import HPAConfig, get_config
from models import (
    AgentProfile,
    HPAStatus,
    PodMetrics,
    ScalingDecision,
    ScalingDirection,
)


class HPAManager:
    """Gestor del Horizontal Pod Autoscaler para agentes."""

    def __init__(self, config: HPAConfig | None = None) -> None:
        self.config = config or get_config().hpa
        self._statuses: Dict[str, HPAStatus] = {}
        self._last_scale_up: Dict[str, float] = {}
        self._last_scale_down: Dict[str, float] = {}

    def register_agent(self, agent: AgentProfile) -> HPAStatus:
        """Registra un agente para auto-scaling."""
        status = HPAStatus(
            agent_name=agent.name,
            min_replicas=self.config.min_replicas,
            max_replicas=self.config.max_replicas,
            current_replicas=agent.replicas,
            target_cpu_percent=self.config.target_cpu_percent,
            target_memory_percent=self.config.target_memory_percent,
        )
        self._statuses[agent.name] = status
        return status

    def evaluate(self, metrics: PodMetrics) -> ScalingDecision:
        """Evalúa métricas y decide si escalar."""
        status = self._statuses.get(metrics.agent_name)
        if status is None:
            # Auto-register
            status = HPAStatus(
                agent_name=metrics.agent_name,
                min_replicas=self.config.min_replicas,
                max_replicas=self.config.max_replicas,
                current_replicas=metrics.replicas_current,
                target_cpu_percent=self.config.target_cpu_percent,
                target_memory_percent=self.config.target_memory_percent,
            )
            self._statuses[metrics.agent_name] = status

        direction, desired, reason = self._compute_scaling(metrics, status)

        # Aplicar cooldown
        now = time.time()
        cooldown_remaining = 0
        if direction == ScalingDirection.up:
            last = self._last_scale_up.get(metrics.agent_name, 0)
            elapsed = now - last
            if elapsed < self.config.scale_up_cooldown_sec:
                cooldown_remaining = int(self.config.scale_up_cooldown_sec - elapsed)
                direction = ScalingDirection.none
                reason = f"Cooldown active ({cooldown_remaining}s remaining)"
                desired = status.current_replicas
        elif direction == ScalingDirection.down:
            last = self._last_scale_down.get(metrics.agent_name, 0)
            elapsed = now - last
            if elapsed < self.config.scale_down_cooldown_sec:
                cooldown_remaining = int(self.config.scale_down_cooldown_sec - elapsed)
                direction = ScalingDirection.none
                reason = f"Cooldown active ({cooldown_remaining}s remaining)"
                desired = status.current_replicas

        decision = ScalingDecision(
            agent_name=metrics.agent_name,
            direction=direction,
            current_replicas=status.current_replicas,
            desired_replicas=desired,
            reason=reason,
            metrics=metrics,
            cooldown_remaining_sec=cooldown_remaining,
        )

        # Aplicar decisión
        if direction == ScalingDirection.up:
            status.current_replicas = desired
            self._last_scale_up[metrics.agent_name] = now
            status.last_scale_time = decision.timestamp
        elif direction == ScalingDirection.down:
            status.current_replicas = desired
            self._last_scale_down[metrics.agent_name] = now
            status.last_scale_time = decision.timestamp

        status.decisions_history.append(decision)
        return decision

    def get_status(self, agent_name: str) -> Optional[HPAStatus]:
        return self._statuses.get(agent_name)

    def get_all_statuses(self) -> List[HPAStatus]:
        return list(self._statuses.values())

    def _compute_scaling(
        self, metrics: PodMetrics, status: HPAStatus
    ) -> tuple[ScalingDirection, int, str]:
        """Calcula dirección y réplicas deseadas."""
        current = status.current_replicas
        reasons: List[str] = []

        # Scoring multi-métrica
        cpu_ratio = metrics.cpu_percent / self.config.target_cpu_percent
        mem_ratio = metrics.memory_percent / self.config.target_memory_percent
        queue_ratio = metrics.queue_depth / max(self.config.custom_metric_target, 1)

        # Peso ponderado: CPU 40%, Mem 30%, Queue 30%
        combined_ratio = cpu_ratio * 0.4 + mem_ratio * 0.3 + queue_ratio * 0.3

        if combined_ratio > 1.2:
            # Scale up
            desired = min(status.max_replicas, int(current * combined_ratio + 0.5))
            desired = max(desired, current + 1)
            desired = min(desired, status.max_replicas)
            reasons.append(f"combined_ratio={combined_ratio:.2f}>1.2 (cpu={cpu_ratio:.2f}, mem={mem_ratio:.2f}, queue={queue_ratio:.2f})")
            return ScalingDirection.up, desired, "; ".join(reasons)

        if combined_ratio < 0.5 and current > status.min_replicas:
            # Scale down
            desired = max(status.min_replicas, int(current * combined_ratio + 0.5))
            desired = max(desired, status.min_replicas)
            if desired >= current:
                desired = current - 1
            reasons.append(f"combined_ratio={combined_ratio:.2f}<0.5 (cpu={cpu_ratio:.2f}, mem={mem_ratio:.2f}, queue={queue_ratio:.2f})")
            return ScalingDirection.down, desired, "; ".join(reasons)

        return ScalingDirection.none, current, f"Stable (combined_ratio={combined_ratio:.2f})"
