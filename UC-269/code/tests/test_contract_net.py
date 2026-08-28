"""Tests unitarios del protocolo Contract Net."""
from __future__ import annotations

import asyncio

from contract_net import ContractNetManager, WorkerAgent
from models import TaskAnnouncement, WorkerProfile


def _default_workers() -> list[WorkerAgent]:
    profiles = [
        WorkerProfile(name="researcher", skills=["feature_extraction"], skill_score=0.95, reliability=0.92, cost_factor=1.4, latency_factor=0.8),
        WorkerProfile(name="coder", skills=["classification"], skill_score=0.85, reliability=0.88, cost_factor=1.1, latency_factor=0.6),
        WorkerProfile(name="reviewer", skills=["validation"], skill_score=0.90, reliability=0.95, cost_factor=1.2, latency_factor=0.7),
    ]
    return [WorkerAgent(profile) for profile in profiles]


def test_worker_proposal_has_score() -> None:
    profile = WorkerProfile(name="test", skill_score=0.8, reliability=0.9, cost_factor=1.0, latency_factor=1.0)
    worker = WorkerAgent(profile)
    task = TaskAnnouncement(title="Test task")
    proposal = asyncio.run(worker.propose(task))
    assert proposal.agent_name == "test"
    assert 0.0 <= proposal.score <= 1.0
    assert proposal.confidence == 0.9


def test_manager_selects_winner() -> None:
    workers = _default_workers()
    manager = ContractNetManager(workers)
    task = asyncio.run(manager.announce("Clasificar patrones"))
    outcome = asyncio.run(manager.run(task))

    assert outcome.status.value == "completed"
    assert len(outcome.proposals) == 3
    assert outcome.winner is not None
    assert outcome.report is not None
    assert outcome.consensus_log.participants == ["researcher", "coder", "reviewer"]


def test_outcome_stored() -> None:
    workers = _default_workers()
    manager = ContractNetManager(workers)
    task = asyncio.run(manager.announce("Otra tarea"))
    outcome = asyncio.run(manager.run(task))
    stored = manager.get_outcome(outcome.task_id)
    assert stored is not None
    assert stored.task_id == outcome.task_id


def test_empty_worker_pool_returns_no_winner() -> None:
    manager = ContractNetManager([])
    task = asyncio.run(manager.announce("Tarea sin workers"))
    outcome = asyncio.run(manager.run(task))
    assert outcome.status.value == "failed"
    assert outcome.winner is None
    assert outcome.report is None
