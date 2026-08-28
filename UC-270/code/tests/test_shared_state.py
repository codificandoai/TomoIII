"""Tests del estado compartido con Propose-Validate-Commit."""
from __future__ import annotations

import pytest

from models import StateProposal
from shared_state import SharedState


def test_propose_validate_commit_success() -> None:
    state = SharedState()
    proposal = StateProposal(agent_name="a", resource_id="R1", proposed_value="owned_by_a", priority_level=0)
    record = state.propose_validate_commit(proposal)
    assert record.committed_value == "owned_by_a"
    assert record.previous_value is None
    assert state.get("R1") == "owned_by_a"


def test_higher_priority_wins() -> None:
    state = SharedState()
    p_low = StateProposal(agent_name="b", resource_id="R1", proposed_value="b_owns", priority_level=2)
    p_high = StateProposal(agent_name="a", resource_id="R1", proposed_value="a_owns", priority_level=0)
    state.propose(p_low)
    state.propose(p_high)
    # Validar high primero: low está pendiente y tiene menor prioridad, no bloquea
    state.validate(p_high.proposal_id)
    record = state.commit(p_high.proposal_id)
    assert record.committed_value == "a_owns"
    # Después del commit de high, p_low fue rechazada automáticamente
    assert p_low.status.value == "rejected"


def test_same_priority_first_come_first_serve() -> None:
    from datetime import datetime, timedelta

    state = SharedState()
    p1 = StateProposal(agent_name="a", resource_id="R1", proposed_value="a", priority_level=1,
                        timestamp=datetime(2026, 1, 1, 10, 0, 0))
    p2 = StateProposal(agent_name="b", resource_id="R1", proposed_value="b", priority_level=1,
                        timestamp=datetime(2026, 1, 1, 10, 0, 1))
    state.propose(p1)
    state.propose(p2)
    state.validate(p1.proposal_id)
    state.validate(p2.proposal_id)
    assert p2.status.value == "rejected"


def test_audit_trail_records_operations() -> None:
    state = SharedState()
    proposal = StateProposal(agent_name="x", resource_id="R1", proposed_value=42, priority_level=0)
    state.propose_validate_commit(proposal)
    trail = state.audit_trail
    assert len(trail) >= 3
    actions = [e.action for e in trail]
    assert "propose" in actions
    assert "validate_ok" in actions
    assert "commit" in actions
    assert all(e.signature is not None for e in trail)
