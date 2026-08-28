"""Orquestador de resolución de conflictos (UC-270).

Pipeline completo:
1. Detectar y clasificar conflictos (OVADARE).
2. Si prioridades difieren → priorización directa.
3. Si prioridades iguales → negociación (NegMAS).
4. Si negociación falla → escalada a autoridad superior.
5. Registrar commit atómico al estado compartido (AutoGen).
6. Auditoría completa con firmas.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional
from uuid import UUID

from config import AppConfig, ResolutionWeights, get_config
from conflict_detector import ConflictDetector
from models import (
    AgentProfile,
    AuditEntry,
    CommitRecord,
    ConflictResolutionOutcome,
    ConflictSeverity,
    ConflictType,
    DetectedConflict,
    NegotiationResult,
    ProposalStatus,
    ResourceClaim,
    ResolutionStatus,
    ResolutionStrategy,
    StateProposal,
)
from negotiation import NegotiationEngine
from shared_state import SharedState


class SuperiorAuthority:
    """Autoridad de escalada que resuelve conflictos por scoring ponderado."""

    def __init__(self, name: str = "arbiter", weights: Optional[ResolutionWeights] = None):
        self.name = name
        self.weights = weights or get_config().weights

    def resolve(
        self,
        conflict: DetectedConflict,
        profiles: Dict[str, AgentProfile],
    ) -> tuple[str, float, str]:
        """Devuelve (winner_name, score, rationale)."""
        best_name = ""
        best_score = -1.0
        for claim in conflict.claims:
            profile = profiles.get(claim.agent_name)
            rep = profile.reputation if profile else 0.5
            score = (
                claim.priority * self.weights.priority
                + claim.need * self.weights.need
                + claim.willingness * self.weights.willingness
                + rep * self.weights.reputation
            )
            if score > best_score:
                best_score = score
                best_name = claim.agent_name

        rationale = (
            f"Escalada resuelta por {self.name}: ganador={best_name} "
            f"con score={best_score:.4f}"
        )
        return best_name, best_score, rationale


class ConflictManager:
    """Orquestador principal del pipeline de resolución."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        authority_name: str = "arbiter",
    ) -> None:
        self.config = config or get_config()
        self.detector = ConflictDetector()
        self.negotiation = NegotiationEngine(self.config.negotiation)
        self.authority = SuperiorAuthority(authority_name, self.config.weights)
        self.state = SharedState()
        self.outcomes: Dict[UUID, ConflictResolutionOutcome] = {}

    def resolve_all(
        self,
        claims: List[ResourceClaim],
        profiles: Dict[str, AgentProfile],
    ) -> List[ConflictResolutionOutcome]:
        """Detecta todos los conflictos y los resuelve."""
        conflicts = self.detector.detect(claims)
        results: List[ConflictResolutionOutcome] = []
        for conflict in conflicts:
            outcome = self.resolve(conflict, profiles)
            results.append(outcome)
        return results

    def resolve(
        self,
        conflict: DetectedConflict,
        profiles: Dict[str, AgentProfile],
    ) -> ConflictResolutionOutcome:
        """Resuelve un conflicto individual usando el pipeline completo."""
        audit: List[AuditEntry] = []
        self._audit(audit, "detect", "system", conflict.resource_id,
                     f"Conflict detected: {conflict.conflict_type.value}, severity={conflict.severity.value}")

        # 1. Priorización directa si prioridades difieren
        priorities = {c.agent_name: c.priority for c in conflict.claims}
        unique_priorities = set(priorities.values())

        if len(unique_priorities) > 1:
            winner = max(priorities, key=lambda k: priorities[k])
            self._audit(audit, "prioritization", "system", conflict.resource_id,
                        f"Resolved by prioritization: {winner}")
            allocation = {winner: 1.0}
            commits = self._commit_winner(conflict, winner, allocation)
            outcome = self._build_outcome(
                conflict, ResolutionStrategy.prioritization, ResolutionStatus.agreement,
                winner, allocation, None, commits, audit,
                f"Resuelto por priorización directa: {winner} (prio={priorities[winner]})"
            )
            self.outcomes[conflict.conflict_id] = outcome
            return outcome

        # 2. Negociación bilateral/multilateral
        self._audit(audit, "negotiate_start", "system", conflict.resource_id,
                    "Starting negotiation (equal priorities)")
        neg_result = self.negotiation.negotiate(conflict, profiles)

        if neg_result.agreement_reached and neg_result.final_allocation:
            winner = max(neg_result.final_allocation, key=lambda k: neg_result.final_allocation[k])
            self._audit(audit, "negotiate_agreement", "system", conflict.resource_id,
                        f"Negotiation succeeded in {neg_result.total_rounds} rounds")
            commits = self._commit_winner(conflict, winner, neg_result.final_allocation)
            outcome = self._build_outcome(
                conflict, ResolutionStrategy.negotiation, ResolutionStatus.agreement,
                winner, neg_result.final_allocation, neg_result, commits, audit,
                f"Acuerdo por negociación en {neg_result.total_rounds} rondas"
            )
            self.outcomes[conflict.conflict_id] = outcome
            return outcome

        # 3. Escalada
        self._audit(audit, "escalate", "system", conflict.resource_id,
                    "Negotiation failed; escalating to authority")
        winner, score, rationale = self.authority.resolve(conflict, profiles)
        allocation = {winner: 1.0}
        commits = self._commit_winner(conflict, winner, allocation)
        self._audit(audit, "escalation_resolved", self.authority.name, conflict.resource_id, rationale)

        outcome = self._build_outcome(
            conflict, ResolutionStrategy.escalation, ResolutionStatus.escalated,
            winner, allocation, neg_result, commits, audit, rationale
        )
        self.outcomes[conflict.conflict_id] = outcome
        return outcome

    def _commit_winner(
        self, conflict: DetectedConflict, winner: str, allocation: Dict[str, float]
    ) -> List[CommitRecord]:
        """Hace commit atómico al estado compartido."""
        commits: List[CommitRecord] = []
        try:
            proposal = StateProposal(
                agent_name=winner,
                resource_id=conflict.resource_id,
                proposed_value={"winner": winner, "allocation": allocation},
                priority_level=0,
            )
            record = self.state.propose_validate_commit(proposal)
            commits.append(record)
        except ValueError:
            pass
        return commits

    def _build_outcome(
        self,
        conflict: DetectedConflict,
        strategy: ResolutionStrategy,
        status: ResolutionStatus,
        winner: Optional[str],
        allocation: Optional[Dict[str, float]],
        negotiation: Optional[NegotiationResult],
        commits: List[CommitRecord],
        audit: List[AuditEntry],
        rationale: str,
    ) -> ConflictResolutionOutcome:
        return ConflictResolutionOutcome(
            conflict_id=conflict.conflict_id,
            conflict_type=conflict.conflict_type,
            severity=conflict.severity,
            resource_id=conflict.resource_id,
            claimants=conflict.claimants,
            strategy=strategy,
            status=status,
            winner=winner,
            allocation=allocation,
            negotiation=negotiation,
            commits=commits,
            audit_trail=audit + self.state.audit_trail,
            rationale=rationale,
            metrics={
                "claims_count": len(conflict.claims),
                "negotiation_rounds": negotiation.total_rounds if negotiation else 0,
                "commits": len(commits),
            },
        )

    def _audit(
        self, trail: List[AuditEntry], action: str, agent: str, resource: str, detail: str
    ) -> None:
        sig = hashlib.sha256(f"{action}:{agent}:{resource}:{detail}".encode()).hexdigest()[:16]
        trail.append(
            AuditEntry(
                action=action,
                agent_name=agent,
                resource_id=resource,
                detail=detail,
                signature=sig,
            )
        )
