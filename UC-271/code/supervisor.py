"""Supervisor Agent para UC-271 — Contract Net con Security y Auto-Scaling.

El supervisor orquesta:
1. Recibe una tarea.
2. Verifica seguridad del contexto.
3. Solicita propuestas a los agentes workers (contract net).
4. Selecciona al mejor agente (scoring).
5. Evalúa métricas y decide si escalar (HPA).
6. Ejecuta la tarea con el ganador.
7. Retorna resultado con contexto de seguridad y decisión de escalado.
"""
from __future__ import annotations

import asyncio
from typing import Dict, List, Optional

from config import AppConfig, get_config
from hpa_manager import HPAManager
from models import (
    AgentProfile,
    AgentRole,
    ExecutionResult,
    HPAStatus,
    PodMetrics,
    Proposal,
    ScalingDecision,
    SecurityContext,
    TaskRequest,
)
from security import SecurityManager


class WorkerAgent:
    """Agente worker que propone y ejecuta tareas."""

    def __init__(self, profile: AgentProfile) -> None:
        self.profile = profile
        self._active_tasks = 0

    @property
    def name(self) -> str:
        return self.profile.name

    async def propose(self, task: str) -> Proposal:
        """Genera una propuesta para la tarea."""
        await asyncio.sleep(self.profile.latency_ms / 1000)
        score = (
            self.profile.skill * 0.50
            + (1.0 / max(self.profile.cost, 0.01)) * 0.25
            + (1.0 / max(self.profile.latency_ms, 1)) * 0.15
            + (1.0 / max(self._active_tasks + 1, 1)) * 0.10
        )
        return Proposal(
            agent_name=self.name,
            role=self.profile.role,
            score=round(score, 6),
            latency_ms=self.profile.latency_ms,
            cost=self.profile.cost,
            message=f"{self.name} ({self.profile.role.value}) propone resolver: {task}",
        )

    async def execute(self, task: str) -> Dict[str, str]:
        """Ejecuta la tarea asignada."""
        self._active_tasks += 1
        await asyncio.sleep(self.profile.latency_ms / 1000)
        self._active_tasks -= 1
        return {
            "agent": self.name,
            "role": self.profile.role.value,
            "result": f"{self.name} ejecutó exitosamente: {task}",
        }

    def get_metrics(self, cpu: float = 50.0, memory: float = 40.0, queue: int = 2) -> PodMetrics:
        """Retorna métricas simuladas del pod."""
        return PodMetrics(
            agent_name=self.name,
            cpu_percent=cpu,
            memory_percent=memory,
            queue_depth=queue,
            active_tasks=self._active_tasks,
            replicas_current=self.profile.replicas,
        )


class SupervisorAgent:
    """Supervisor que orquesta workers con seguridad y auto-scaling."""

    def __init__(
        self,
        workers: List[WorkerAgent],
        config: AppConfig | None = None,
    ) -> None:
        self.config = config or get_config()
        self.workers = workers
        self.security = SecurityManager(self.config.security, self.config.namespace)
        self.hpa = HPAManager(self.config.hpa)
        # Registrar workers en HPA
        for w in workers:
            self.hpa.register_agent(w.profile)

    async def run_task(self, request: TaskRequest) -> ExecutionResult:
        """Pipeline completo: security → contract net → HPA → execute."""
        # 1. Generar contexto de seguridad para la ejecución
        security_ctx = SecurityContext()

        # 2. Contract Net: solicitar propuestas
        proposals = await asyncio.gather(*(w.propose(request.task) for w in self.workers))
        proposals = list(proposals)

        if not proposals:
            return ExecutionResult(
                task_id=request.task_id,
                task=request.task,
                winner="none",
                proposals=[],
                execution={"error": "No workers available"},
                security_context=security_ctx,
            )

        # 3. Seleccionar ganador
        best = max(proposals, key=lambda p: p.score)
        winner = next(w for w in self.workers if w.name == best.agent_name)

        # 4. Evaluar HPA con métricas del ganador
        metrics = winner.get_metrics()
        scaling_decision = self.hpa.evaluate(metrics)

        # 5. Ejecutar tarea
        execution = await winner.execute(request.task)

        return ExecutionResult(
            task_id=request.task_id,
            task=request.task,
            winner=best.agent_name,
            proposals=proposals,
            execution=execution,
            scaling_decision=scaling_decision,
            security_context=security_ctx,
        )

    def get_hpa_statuses(self) -> List[HPAStatus]:
        return self.hpa.get_all_statuses()

    def get_security_audit(self) -> List[Dict]:
        return [e.model_dump(mode="json") for e in self.security.audit_trail]
