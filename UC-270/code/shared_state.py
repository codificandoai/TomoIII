"""Estado compartido con Propose-Validate-Commit atómico (inspirado en AutoGen) para UC-270.

Los agentes no escriben directo al estado; proponen, el sistema valida y hace
commit atómico. A igual prioridad, primero en llegar gana. Cada cambio queda
registrado con agente, timestamp y firma.
"""
from __future__ import annotations

import hashlib
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from models import (
    AuditEntry,
    CommitRecord,
    ProposalStatus,
    StateProposal,
)


class SharedState:
    """Estado compartido con commit atómico y auditoría."""

    def __init__(self) -> None:
        self._state: Dict[str, Any] = {}
        self._pending: Dict[UUID, StateProposal] = {}
        self._commits: List[CommitRecord] = []
        self._audit: List[AuditEntry] = []
        self._lock = threading.Lock()

    def propose(self, proposal: StateProposal) -> StateProposal:
        """Registra una propuesta de escritura al estado."""
        with self._lock:
            self._pending[proposal.proposal_id] = proposal
            self._audit_log("propose", proposal.agent_name, proposal.resource_id,
                            f"Proposed value={proposal.proposed_value}, priority={proposal.priority_level}")
        return proposal

    def validate(self, proposal_id: UUID) -> StateProposal:
        """Valida una propuesta contra el estado actual y conflictos pendientes."""
        with self._lock:
            proposal = self._pending.get(proposal_id)
            if proposal is None:
                raise ValueError(f"Proposal {proposal_id} not found")

            # Verificar si hay otra propuesta pendiente con mayor prioridad para el mismo recurso
            for pid, other in self._pending.items():
                if (
                    pid != proposal_id
                    and other.resource_id == proposal.resource_id
                    and other.status in (ProposalStatus.proposed, ProposalStatus.validated)
                    and other.priority_level < proposal.priority_level
                ):
                    proposal.status = ProposalStatus.rejected
                    self._audit_log(
                        "validate_rejected", proposal.agent_name, proposal.resource_id,
                        f"Rejected: higher priority proposal from {other.agent_name}"
                    )
                    return proposal

                # A igual prioridad, primero en llegar gana
                if (
                    pid != proposal_id
                    and other.resource_id == proposal.resource_id
                    and other.status in (ProposalStatus.proposed, ProposalStatus.validated)
                    and other.priority_level == proposal.priority_level
                    and other.timestamp < proposal.timestamp
                ):
                    proposal.status = ProposalStatus.rejected
                    self._audit_log(
                        "validate_rejected", proposal.agent_name, proposal.resource_id,
                        f"Rejected: same priority but {other.agent_name} arrived first"
                    )
                    return proposal

            proposal.status = ProposalStatus.validated
            self._audit_log("validate_ok", proposal.agent_name, proposal.resource_id, "Validated")
            return proposal

    def commit(self, proposal_id: UUID) -> CommitRecord:
        """Hace commit atómico de una propuesta validada."""
        with self._lock:
            proposal = self._pending.get(proposal_id)
            if proposal is None:
                raise ValueError(f"Proposal {proposal_id} not found")
            if proposal.status != ProposalStatus.validated:
                raise ValueError(f"Proposal {proposal_id} not validated (status={proposal.status})")

            previous = self._state.get(proposal.resource_id)
            self._state[proposal.resource_id] = proposal.proposed_value
            proposal.status = ProposalStatus.committed

            record = CommitRecord(
                proposal_id=proposal_id,
                agent_name=proposal.agent_name,
                resource_id=proposal.resource_id,
                committed_value=proposal.proposed_value,
                previous_value=previous,
            )
            self._commits.append(record)

            # Rechazar otras propuestas pendientes para el mismo recurso
            for pid, other in self._pending.items():
                if (
                    pid != proposal_id
                    and other.resource_id == proposal.resource_id
                    and other.status in (ProposalStatus.proposed, ProposalStatus.validated)
                ):
                    other.status = ProposalStatus.rejected

            self._audit_log(
                "commit", proposal.agent_name, proposal.resource_id,
                f"Committed value={proposal.proposed_value}, prev={previous}"
            )
            return record

    def propose_validate_commit(self, proposal: StateProposal) -> CommitRecord:
        """Atajo: propose → validate → commit en una transacción."""
        self.propose(proposal)
        self.validate(proposal.proposal_id)
        if proposal.status == ProposalStatus.rejected:
            raise ValueError(f"Proposal rejected for {proposal.resource_id}")
        return self.commit(proposal.proposal_id)

    def get(self, resource_id: str) -> Any:
        return self._state.get(resource_id)

    @property
    def commits(self) -> List[CommitRecord]:
        return list(self._commits)

    @property
    def audit_trail(self) -> List[AuditEntry]:
        return list(self._audit)

    def _audit_log(self, action: str, agent: str, resource: str, detail: str) -> None:
        sig = hashlib.sha256(f"{action}:{agent}:{resource}:{detail}".encode()).hexdigest()[:16]
        self._audit.append(
            AuditEntry(
                action=action,
                agent_name=agent,
                resource_id=resource,
                detail=detail,
                signature=sig,
            )
        )
