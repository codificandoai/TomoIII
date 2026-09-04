"""UC-313 — Middleware de difusión y ventanas temporales para Contract Net Protocol (CNP).

Combina el protocolo Contract Net con la capa de plasticidad UC-307:
- Un manager difunde una tarea.
- Agentes (workers) responden con propuestas.
- La capa de evolución evalúa cada propuesta y decide sobre los agentes
  (persistir, ajustar, mutar, eliminar, reproducir).
- Las rondas se agrupan en ventanas temporales para análisis de desempeño y
  toma de decisiones a nivel de población.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from cognitive_evolution_layer import (
    ExecutionObservation,
    PlasticityDecision,
    UC307CognitiveEvolutionLayer,
)
from memory_router import IntelligentMemoryRouter


@dataclass
class CNPAgentProfile:
    """Perfil de un agente participante en CNP."""

    agent_id: str
    skills: List[str] = field(default_factory=list)
    reliability: float = 0.9
    cost_factor: float = 1.0
    latency_factor: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "skills": self.skills,
            "reliability": self.reliability,
            "cost_factor": self.cost_factor,
            "latency_factor": self.latency_factor,
        }


@dataclass
class CNPProposal:
    """Propuesta enviada por un agente."""

    agent_id: str
    task_id: str
    bid_score: float  # score de calidad normalizado 0..1
    estimated_cost: float
    estimated_latency_ms: float
    confidence: float
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "bid_score": self.bid_score,
            "estimated_cost": self.estimated_cost,
            "estimated_latency_ms": self.estimated_latency_ms,
            "confidence": self.confidence,
            "message": self.message,
            "timestamp": self.timestamp,
        }


@dataclass
class CNPRound:
    """Una ronda completa de anuncio, propuestas y adjudicación."""

    round_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_id: str = ""
    task_description: str = ""
    proposals: List[CNPProposal] = field(default_factory=list)
    winner_id: Optional[str] = None
    award_score: float = 0.0
    status: str = "announced"  # announced, bidding, awarded, completed
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    evolution_decisions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_id": self.round_id,
            "task_id": self.task_id,
            "task_description": self.task_description,
            "proposals": [p.to_dict() for p in self.proposals],
            "winner_id": self.winner_id,
            "award_score": self.award_score,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "evolution_decisions": self.evolution_decisions,
        }


class ContractNetMiddleware:
    """Middleware CNP + UC-307 para coordinar y evolucionar una población de agentes."""

    def __init__(
        self,
        agents: Optional[List[CNPAgentProfile]] = None,
        evolution_layer: Optional[UC307CognitiveEvolutionLayer] = None,
        memory_router: Optional[IntelligentMemoryRouter] = None,
        window_size: int = 5,
    ) -> None:
        self.agents: Dict[str, CNPAgentProfile] = {a.agent_id: a for a in (agents or [])}
        self.evolution = evolution_layer or UC307CognitiveEvolutionLayer()
        self.memory_router = memory_router or IntelligentMemoryRouter()
        self.window_size = window_size
        self.rounds: List[CNPRound] = []
        self.current_window: List[CNPRound] = []

    def register_agent(self, profile: CNPAgentProfile) -> None:
        self.agents[profile.agent_id] = profile

    def broadcast_task(
        self,
        task_id: str,
        description: str,
        requirements: Optional[Dict[str, Any]] = None,
    ) -> CNPRound:
        """Difunde una tarea a todos los agentes registrados."""
        round_ = CNPRound(
            task_id=task_id,
            task_description=description,
            status="announced",
        )
        # Persistir anuncio como nota de trabajo
        self.memory_router.store_working_memory(
            f"CNP announce {task_id}: {description}",
            note_type="cnp_announce",
            metadata={"requirements": requirements or {}},
        )
        return round_

    def collect_proposals(
        self,
        round_: CNPRound,
        simulated: bool = True,
    ) -> CNPRound:
        """Recoge propuestas de los agentes (simuladas o reales)."""
        round_.status = "bidding"
        proposals: List[CNPProposal] = []
        for agent_id, profile in self.agents.items():
            if simulated:
                proposal = self._simulate_proposal(agent_id, round_.task_id, profile)
            else:
                proposal = self._request_proposal(agent_id, round_)
            proposals.append(proposal)
        round_.proposals = proposals
        return round_

    def _simulate_proposal(
        self,
        agent_id: str,
        task_id: str,
        profile: CNPAgentProfile,
    ) -> CNPProposal:
        import random
        # Calidad depende de fiabilidad y especialización
        base = profile.reliability
        noise = random.uniform(-0.15, 0.15)
        bid_score = min(1.0, max(0.0, base + noise))
        return CNPProposal(
            agent_id=agent_id,
            task_id=task_id,
            bid_score=bid_score,
            estimated_cost=profile.cost_factor * random.uniform(0.5, 1.5),
            estimated_latency_ms=profile.latency_factor * random.uniform(50, 500),
            confidence=bid_score,
            message=f"Propuesta simulada de {agent_id}",
        )

    def _request_proposal(self, agent_id: str, round_: CNPRound) -> CNPProposal:
        # Placeholder para integración real: llamada HTTP/RPC al agente
        profile = self.agents[agent_id]
        return self._simulate_proposal(agent_id, round_.task_id, profile)

    def evaluate_and_award(self, round_: CNPRound, execution_success: bool = True) -> CNPRound:
        """Evalúa propuestas con UC-307, adjudica y toma decisiones evolutivas."""
        round_.status = "awarded"
        if not round_.proposals:
            round_.status = "completed"
            round_.completed_at = datetime.now(timezone.utc).isoformat()
            return round_

        # Seleccionar ganador por score ponderado
        def score(p: CNPProposal) -> float:
            return (
                0.5 * p.bid_score
                + 0.3 * p.confidence
                - 0.1 * p.estimated_cost
                - 0.1 * (p.estimated_latency_ms / 1000.0)
            )

        winner = max(round_.proposals, key=score)
        round_.winner_id = winner.agent_id
        round_.award_score = score(winner)

        # Evaluar cada agente con la capa de plasticidad
        for proposal in round_.proposals:
            is_winner = proposal.agent_id == winner.agent_id
            obs = ExecutionObservation(
                agent_id=proposal.agent_id,
                task_id=round_.task_id,
                success=execution_success and is_winner,
                reward=proposal.bid_score if is_winner else -0.2,
                latency_seconds=proposal.estimated_latency_ms / 1000.0,
                tool_calls=1,
                confidence=proposal.confidence,
                coherence=proposal.bid_score,
                context={
                    "task_description": round_.task_description,
                    "bid_score": proposal.bid_score,
                    "is_winner": is_winner,
                },
            )
            result = self.evolution.evaluate_execution(obs)
            # Actualizar pesos sinápticos del agente
            self.evolution.update_synaptic_weights(
                proposal.agent_id,
                success=obs.success,
                confidence=proposal.confidence,
            )
            round_.evolution_decisions.append({
                "agent_id": proposal.agent_id,
                "decision": result.decision.value,
                "fitness": result.fitness,
                "actions": result.actions,
            })

        round_.status = "completed"
        round_.completed_at = datetime.now(timezone.utc).isoformat()
        self.rounds.append(round_)
        self._add_to_window(round_)
        return round_

    def _add_to_window(self, round_: CNPRound) -> None:
        self.current_window.append(round_)
        if len(self.current_window) > self.window_size:
            self.current_window.pop(0)

    def window_summary(self) -> Dict[str, Any]:
        """Resumen de desempeño de la ventana temporal actual."""
        if not self.current_window:
            return {"rounds": 0, "avg_fitness": 0.0, "winners": []}
        fitnesses: List[float] = []
        winners: List[str] = []
        for r in self.current_window:
            for d in r.evolution_decisions:
                fitnesses.append(d["fitness"])
            if r.winner_id:
                winners.append(r.winner_id)
        avg_fitness = sum(fitnesses) / len(fitnesses) if fitnesses else 0.0
        return {
            "rounds": len(self.current_window),
            "avg_fitness": round(avg_fitness, 4),
            "winners": winners,
            "agent_count": len(self.agents),
        }

    def run_round(
        self,
        task_id: str,
        description: str,
        execution_success: bool = True,
        requirements: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Pipeline completo: anunciar, recoger, adjudicar y evolucionar."""
        round_ = self.broadcast_task(task_id, description, requirements)
        round_ = self.collect_proposals(round_, simulated=True)
        round_ = self.evaluate_and_award(round_, execution_success=execution_success)
        return {
            "round": round_.to_dict(),
            "window_summary": self.window_summary(),
            "synaptic_weights": self.evolution.get_synaptic_snapshot(),
            "homeostasis": self.evolution.check_homeostasis().to_dict(),
        }

    def broadcast_state(self) -> Dict[str, Any]:
        """Publica el estado evolutivo actual para otros módulos/agentes."""
        return self.evolution.broadcast_state(source="cnp_middleware")
