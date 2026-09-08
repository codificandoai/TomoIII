"""UC-317 — Tests for AgentKernel safe-shutdown wrappers."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_kernel import AgentKernel
from agent_scheduler import AgentScheduler


def test_kernel_stop_and_drain_delegates_to_scheduler():
    kernel = AgentKernel()
    kernel.scheduler.schedule("agent-1", "goal-1")
    kernel.scheduler.schedule("agent-2", "goal-2")

    result = kernel.stop_accepting_tasks("sd-317-001")
    assert result["stopped"] is True

    drain = kernel.drain_and_cancel("sd-317-001", timeout_seconds=5.0)
    assert drain["cancelled"] == 2
    assert not kernel.is_accepting_tasks()


def test_kernel_resume_accepting_tasks():
    kernel = AgentKernel()
    kernel.stop_accepting_tasks("sd-317-002")
    assert not kernel.is_accepting_tasks()
    kernel.resume_accepting_tasks()
    assert kernel.is_accepting_tasks()
