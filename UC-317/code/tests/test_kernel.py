"""Tests unitarios para UC-317 — AIOS-style Agent Kernel."""
import json
import os
import sys

import pytest

# Añadir el directorio code/ al path para imports.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# -----------------------------------------------------------------------------
# LLM Core
# -----------------------------------------------------------------------------
def test_llm_core_mock_backend():
    from kernel_config import KernelConfig
    from llm_core import LLMCore

    kernel_cfg = KernelConfig.default()
    core = LLMCore(kernel_cfg)
    response = core.generate([{"role": "user", "content": "hello"}])
    assert response.content
    assert response.provider == "mock"
    assert response.usage["total_tokens"] > 0


def test_llm_core_list_models():
    from kernel_config import KernelConfig
    from llm_core import LLMCore

    core = LLMCore(KernelConfig.default())
    models = core.list_models()
    assert any(m["name"] == "mock" for m in models)


# -----------------------------------------------------------------------------
# Memory Manager
# -----------------------------------------------------------------------------
def test_memory_add_and_retrieve():
    from memory_manager import MemoryManager

    mgr = MemoryManager()
    mgr.add("agent_1", "The user prefers Spanish.", long_term=True)
    mgr.add("agent_1", "Hello, how are you?")
    retrieved = mgr.retrieve("agent_1", "Spanish")
    assert retrieved
    assert "Spanish" in retrieved[0].content


def test_memory_context():
    from memory_manager import MemoryManager

    mgr = MemoryManager()
    mgr.add("agent_1", "msg1", role="user")
    mgr.add("agent_1", "msg2", role="assistant")
    ctx = mgr.get_context("agent_1")
    assert len(ctx) == 2
    assert ctx[0]["role"] == "user"


def test_memory_clear():
    from memory_manager import MemoryManager

    mgr = MemoryManager()
    mgr.add("agent_1", "hello")
    mgr.clear("agent_1")
    assert mgr.get_context("agent_1") == []


# -----------------------------------------------------------------------------
# Tool Manager
# -----------------------------------------------------------------------------
def test_tool_calculator():
    from tool_manager import ToolManager

    tm = ToolManager()
    result = tm.call("calculator", {"expression": "2+2"})
    assert result["success"]
    assert result["result"] == 4


def test_tool_calculator_unsafe():
    from tool_manager import ToolManager

    tm = ToolManager()
    result = tm.call("calculator", {"expression": "__import__('os')"})
    assert not result["success"]


def test_tool_search():
    from tool_manager import ToolManager

    tm = ToolManager()
    result = tm.call("search", {"query": "AIOS"})
    assert result["success"]
    assert "results" in result["result"]


def test_tool_not_found():
    from tool_manager import ToolManager

    tm = ToolManager()
    result = tm.call("nonexistent", {})
    assert not result["success"]


def test_tool_list():
    from tool_manager import ToolManager

    tm = ToolManager()
    tools = tm.list_tools()
    assert any(t["name"] == "calculator" for t in tools)


# -----------------------------------------------------------------------------
# Storage Manager
# -----------------------------------------------------------------------------
def test_storage_save_load():
    from storage_manager import StorageManager

    sm = StorageManager(base_dir="/tmp/uc317_test_storage")
    sm.save("test_key", {"value": 42})
    loaded = sm.load("test_key")
    assert loaded["value"] == 42


def test_storage_delete():
    from storage_manager import StorageManager

    sm = StorageManager(base_dir="/tmp/uc317_test_storage")
    sm.save("to_delete", {"x": 1})
    assert sm.delete("to_delete")
    assert sm.load("to_delete") is None


# -----------------------------------------------------------------------------
# Access Manager
# -----------------------------------------------------------------------------
def test_access_guest_denied_tool():
    from access_manager import AccessManager, Permission

    am = AccessManager()
    assert not am.has_permission(["guest"], Permission.TOOL_USE)


def test_access_user_allowed_tool():
    from access_manager import AccessManager, Permission

    am = AccessManager()
    assert am.has_permission(["user"], Permission.TOOL_USE)


def test_access_risk_levels():
    from access_manager import AccessManager

    am = AccessManager()
    assert am.allowed_risk(["user"], "medium")
    assert not am.allowed_risk(["user"], "critical")


# -----------------------------------------------------------------------------
# Agent Scheduler
# -----------------------------------------------------------------------------
def test_scheduler_basic():
    from agent_scheduler import AgentScheduler

    sched = AgentScheduler(max_concurrent=2)

    def runner(agent_id, goal):
        return {"done": True}

    sched.schedule("a1", "g1")
    sched.schedule("a2", "g2")
    sched.tick(runner)
    status = sched.status()
    assert status["completed"] == 2


# -----------------------------------------------------------------------------
# Agent Kernel
# -----------------------------------------------------------------------------
def test_kernel_create_session():
    from agent_kernel import AgentKernel

    kernel = AgentKernel()
    session = kernel.create_session(name="test", roles=["user"])
    assert session.agent_id.startswith("agent_")
    assert kernel.get_session(session.agent_id) is not None


def test_kernel_chat():
    from agent_kernel import AgentKernel

    kernel = AgentKernel()
    session = kernel.create_session(name="test", model="mock")
    result = kernel.chat(session.agent_id, "hello")
    assert result["response"]
    assert result["provider"] == "mock"


def test_kernel_syscall_llm():
    from agent_kernel import AgentKernel
    from syscalls import SyscallRequest, SyscallType, SyscallOp

    kernel = AgentKernel()
    session = kernel.create_session(name="test", roles=["user"])
    req = SyscallRequest(
        syscall_type=SyscallType.LLM,
        operation=SyscallOp.LLM_GENERATE,
        payload={"messages": [{"role": "user", "content": "hello"}]},
        agent_id=session.agent_id,
    )
    resp = kernel.syscall(req)
    assert resp.success


def test_kernel_syscall_permission_denied():
    from agent_kernel import AgentKernel
    from syscalls import SyscallRequest, SyscallType, SyscallOp

    kernel = AgentKernel()
    session = kernel.create_session(name="test", roles=["guest"])
    req = SyscallRequest(
        syscall_type=SyscallType.TOOL,
        operation=SyscallOp.TOOL_CALL,
        payload={"name": "calculator", "args": {"expression": "1+1"}},
        agent_id=session.agent_id,
    )
    resp = kernel.syscall(req)
    assert not resp.success
    assert "Permission denied" in resp.error


def test_kernel_syscall_storage():
    from agent_kernel import AgentKernel
    from syscalls import SyscallRequest, SyscallType, SyscallOp

    kernel = AgentKernel()
    session = kernel.create_session(name="test", roles=["developer"])
    req = SyscallRequest(
        syscall_type=SyscallType.STORAGE,
        operation=SyscallOp.STORAGE_SAVE,
        payload={"key": "k1", "data": {"v": 1}},
        agent_id=session.agent_id,
    )
    resp = kernel.syscall(req)
    assert resp.success
