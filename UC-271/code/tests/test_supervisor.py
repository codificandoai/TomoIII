"""Tests del supervisor agent."""
from __future__ import annotations

import asyncio

from models import AgentProfile, AgentRole, TaskRequest
from supervisor import SupervisorAgent, WorkerAgent


def _make_workers() -> list[WorkerAgent]:
    profiles = [
        AgentProfile(name="a", role=AgentRole.researcher, skill=0.9, cost=1.0, latency_ms=50, replicas=1, service_account="a-sa"),
        AgentProfile(name="b", role=AgentRole.coder, skill=0.85, cost=0.8, latency_ms=40, replicas=1, service_account="b-sa"),
    ]
    return [WorkerAgent(p) for p in profiles]


def test_supervisor_selects_best_proposal() -> None:
    workers = _make_workers()
    supervisor = SupervisorAgent(workers)
    req = TaskRequest(task="test task", priority=5)
    result = asyncio.run(supervisor.run_task(req))
    assert result.winner in ("a", "b")
    assert len(result.proposals) == 2
    assert result.execution["result"] is not None


def test_supervisor_returns_scaling_decision() -> None:
    workers = _make_workers()
    supervisor = SupervisorAgent(workers)
    req = TaskRequest(task="scaling test", priority=7)
    result = asyncio.run(supervisor.run_task(req))
    assert result.scaling_decision is not None
    assert result.scaling_decision.agent_name in ("a", "b")


def test_supervisor_returns_security_context() -> None:
    workers = _make_workers()
    supervisor = SupervisorAgent(workers)
    req = TaskRequest(task="security test")
    result = asyncio.run(supervisor.run_task(req))
    assert result.security_context is not None
    assert result.security_context.run_as_non_root is True


def test_supervisor_no_workers() -> None:
    supervisor = SupervisorAgent([])
    req = TaskRequest(task="no workers")
    result = asyncio.run(supervisor.run_task(req))
    assert result.winner == "none"
    assert "error" in result.execution
