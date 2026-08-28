"""Implementación del protocolo Contract Net para UC-269."""
from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from config import AppConfig, get_config
from metrics import METRICS
from models import (
    ConsensusLog,
    ContractAward,
    ContractNetOutcome,
    ExecutionReport,
    Proposal,
    TaskAnnouncement,
    TaskStatus,
    WorkerProfile,
)


class WorkerAgent:
    """Worker que evalúa una tarea y presenta una propuesta."""

    def __init__(self, profile: WorkerProfile, rng_jitter: float = 0.05):
        self.profile = profile
        self.rng_jitter = rng_jitter

    async def propose(self, task: TaskAnnouncement) -> Proposal:
        """Genera una propuesta para la tarea anunciada."""
        # Simula tiempo de estimación
        await asyncio.sleep(0.01)

        # Puntuación heurística: alta habilidad, bajo costo, baja latencia, alta fiabilidad
        profile = self.profile
        cost_score = 1.0 / max(profile.cost_factor, 1e-6)
        latency_score = 1.0 / max(profile.latency_factor, 1e-6)
        score = (
            profile.skill_score * 0.5
            + cost_score * 0.25
            + latency_score * 0.15
            + profile.reliability * 0.10
        )
        # Normaliza a [0, 1] con un pequeño jitter
        score = max(0.0, min(1.0, score + self._jitter()))

        estimated_cost = Decimal(f"{profile.cost_factor * 100:.2f}")
        estimated_latency_ms = int(profile.latency_factor * 1000)

        return Proposal(
            task_id=task.task_id,
            agent_name=profile.name,
            score=score,
            estimated_cost=estimated_cost,
            estimated_latency_ms=estimated_latency_ms,
            confidence=profile.reliability,
            message=f"{profile.name} propone resolver: {task.title}",
        )

    async def execute(self, task: TaskAnnouncement) -> ExecutionReport:
        """Ejecuta la tarea adjudicada y reporta el resultado."""
        start = time.perf_counter()
        # Simula trabajo
        await asyncio.sleep(0.05)
        duration_ms = int((time.perf_counter() - start) * 1000)

        # Falla ocasional si fiabilidad baja
        if self.profile.reliability < 0.7 and hash(task.task_id) % 100 < 10:
            return ExecutionReport(
                task_id=task.task_id,
                agent_name=self.profile.name,
                status="failed",
                result="",
                execution_time_ms=duration_ms,
                error="Simulated execution failure",
            )

        return ExecutionReport(
            task_id=task.task_id,
            agent_name=self.profile.name,
            status="success",
            result=f"{self.profile.name} ejecutó la tarea: {task.title}",
            execution_time_ms=duration_ms,
            cost_incurred=Decimal(f"{self.profile.cost_factor * 95:.2f}"),
        )

    def _jitter(self) -> float:
        import random

        return random.uniform(-self.rng_jitter, self.rng_jitter)


class ContractNetManager:
    """Manager que coordina una ronda del protocolo Contract Net."""

    def __init__(
        self,
        workers: List[WorkerAgent],
        config: Optional[AppConfig] = None,
        name: str = "contract-net-manager",
    ) -> None:
        self.workers = workers
        self.config = config or get_config()
        self.name = name
        self.outcomes: Dict[UUID, ContractNetOutcome] = {}

    async def announce(self, title: str, description: str = "", **requirements: Any) -> TaskAnnouncement:
        """Crea y retorna un anuncio."""
        announcement = TaskAnnouncement(
            title=title,
            description=description,
            requirements=requirements,
            status=TaskStatus.announced,
        )
        return announcement

    async def run(self, task: TaskAnnouncement) -> ContractNetOutcome:
        """Ejecuta el ciclo completo: anuncio → propuestas → adjudicación → ejecución."""
        METRICS.inc_tasks(status="started")
        task.status = TaskStatus.bidding

        # 1. Solicitar propuestas concurrentemente
        proposals = await asyncio.gather(
            *(w.propose(task) for w in self.workers),
            return_exceptions=True,
        )
        valid_proposals: List[Proposal] = []
        for p in proposals:
            if isinstance(p, Exception):
                METRICS.inc_results(status="proposal_error")
                continue
            valid_proposals.append(p)
            METRICS.inc_proposals(agent=p.agent_name)

        # 2. Seleccionar la mejor propuesta
        winner, award = self._select_winner(task, valid_proposals)

        if winner is None:
            task.status = TaskStatus.failed
            outcome = self._build_outcome(
                task, valid_proposals, winner=None, award=None, report=None
            )
            METRICS.inc_tasks(status="no_winner")
            self.outcomes[task.task_id] = outcome
            return outcome

        task.status = TaskStatus.awarded
        METRICS.observe_selection_score(score=award.award_score if award else 0.0)

        # 3. Ejecutar tarea
        task.status = TaskStatus.executing
        start = time.perf_counter()
        report = await winner.execute(task)
        duration_s = time.perf_counter() - start
        METRICS.observe_execution_duration(seconds=duration_s)

        if report.status == "success":
            METRICS.inc_results(status="success")
            METRICS.inc_tasks(status="completed")
        else:
            METRICS.inc_results(status="failed")
            METRICS.inc_tasks(status="failed")

        task.status = TaskStatus.completed if report.status == "success" else TaskStatus.failed

        outcome = self._build_outcome(task, valid_proposals, winner, award, report)
        self.outcomes[task.task_id] = outcome
        return outcome

    def _select_winner(
        self, task: TaskAnnouncement, proposals: List[Proposal]
    ) -> tuple[Optional[WorkerAgent], Optional[ContractAward]]:
        if not proposals:
            return None, None
        best = max(proposals, key=lambda p: p.score)
        winner = next((w for w in self.workers if w.profile.name == best.agent_name), None)
        if winner is None:
            return None, None
        award = ContractAward(
            task_id=task.task_id,
            proposal_id=best.proposal_id,
            winner_name=best.agent_name,
            award_score=best.score,
        )
        return winner, award

    def _build_outcome(
        self,
        task: TaskAnnouncement,
        proposals: List[Proposal],
        winner: Optional[WorkerAgent],
        award: Optional[ContractAward],
        report: Optional[ExecutionReport],
    ) -> ContractNetOutcome:
        consensus = ConsensusLog(
            task_id=task.task_id,
            manager_name=self.name,
            participants=[w.profile.name for w in self.workers],
            proposals=proposals,
            winner=winner.profile.name if winner else None,
            award=award,
            report=report,
            consensus_score=award.award_score if award else 0.0,
            status=task.status,
        )
        return ContractNetOutcome(
            task_id=task.task_id,
            task_title=task.title,
            status=task.status,
            proposals=proposals,
            winner=winner.profile.name if winner else None,
            award=award,
            report=report,
            consensus_log=consensus,
            metrics={
                "worker_count": len(self.workers),
                "proposal_count": len(proposals),
                "weights": self.config.weights.as_dict,
            },
        )

    def get_outcome(self, task_id: UUID) -> Optional[ContractNetOutcome]:
        return self.outcomes.get(task_id)
