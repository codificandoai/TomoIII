"""Tests del middleware CNP + plasticidad UC-313."""
from __future__ import annotations

from cnp_broadcast_middleware import CNPAgentProfile, ContractNetMiddleware


def test_broadcast_and_collect():
    cnp = ContractNetMiddleware(agents=[
        CNPAgentProfile("a1", skills=["x"], reliability=0.9),
        CNPAgentProfile("a2", skills=["y"], reliability=0.7),
    ])
    round_ = cnp.broadcast_task("t1", "test task")
    round_ = cnp.collect_proposals(round_)
    assert len(round_.proposals) == 2


def test_award_and_evolve():
    cnp = ContractNetMiddleware(agents=[
        CNPAgentProfile("a1", skills=["x"], reliability=0.9),
    ])
    result = cnp.run_round("t1", "test", execution_success=True)
    assert result["round"]["status"] == "completed"
    assert result["round"]["winner_id"] == "a1"
    assert result["round"]["evolution_decisions"]


def test_window_summary():
    cnp = ContractNetMiddleware(
        agents=[CNPAgentProfile("a1", skills=["x"], reliability=0.9)],
        window_size=3,
    )
    for i in range(4):
        cnp.run_round(f"t{i}", "task", execution_success=True)
    summary = cnp.window_summary()
    assert summary["rounds"] == 3


def test_synaptic_weights_updated():
    cnp = ContractNetMiddleware(agents=[
        CNPAgentProfile("a1", skills=["x"], reliability=0.9),
    ])
    cnp.run_round("t1", "task", execution_success=True)
    weights = cnp.evolution.get_synaptic_snapshot()
    assert "a1" in weights["weights"]
