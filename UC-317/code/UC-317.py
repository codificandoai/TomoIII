"""
Codificando.AI
UC-317: AIOS-style Agent Kernel & Runtime — capa de ejecución/orquestación
         para agentes de IA con modelos intercambiables, tools, memoria,
         storage y syscalls bajo una interfaz común.

Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.
"""
from __future__ import annotations

import argparse
import json
import sys

from agent_kernel import AgentKernel
from kernel_config import KernelConfig


def _print(label: str, payload) -> None:
    print(f"\n-- {label} --")
    if isinstance(payload, (dict, list)):
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        print(payload)


def demo_basic_chat() -> None:
    print("\n== Demo: Basic agent chat (mock LLM) ==")
    kernel = AgentKernel()
    session = kernel.create_session(name="demo-agent", roles=["user"], model="mock")
    _print("Session created", {"agent_id": session.agent_id, "name": session.name})

    result = kernel.chat(session.agent_id, "hello")
    _print("Chat result", result)
    assert result["response"]


def demo_tool_use() -> None:
    print("\n== Demo: Tool use (calculator) ==")
    kernel = AgentKernel()
    session = kernel.create_session(name="calc-agent", roles=["user"], model="mock")
    _print("Session", {"agent_id": session.agent_id})

    result = kernel.chat(session.agent_id, "Please use the calculator to compute 2+2")
    _print("Chat result", result)
    # Mock LLM no detecta tool por contenido; invocamos manualmente.
    calc_result = kernel.tools.call("calculator", {"expression": "2+2"})
    _print("Calculator result", calc_result)
    assert calc_result["success"]
    assert calc_result["result"] == 4


def demo_memory() -> None:
    print("\n== Demo: Memory persistence ==")
    kernel = AgentKernel()
    session = kernel.create_session(name="memory-agent", roles=["user"], model="mock")

    kernel.memory.add(session.agent_id, "The user prefers Spanish.", role="user", source="conversation", long_term=True)
    kernel.memory.add(session.agent_id, "Hello, how are you?", role="user", source="conversation")

    context = kernel.memory.get_context(session.agent_id)
    _print("Context messages", context)
    assert any("Spanish" in m["content"] for m in context)

    retrieved = kernel.memory.retrieve(session.agent_id, "Spanish", top_k=1)
    _print("Retrieved", [e.content for e in retrieved])
    assert retrieved


def demo_storage() -> None:
    print("\n== Demo: Storage ==")
    kernel = AgentKernel()
    session = kernel.create_session(name="storage-agent", roles=["developer"], model="mock")

    kernel.storage.save("agent_state", {"counter": 1, "last_goal": "demo"})
    loaded = kernel.storage.load("agent_state")
    _print("Loaded from storage", loaded)
    assert loaded["counter"] == 1


def demo_scheduler() -> None:
    print("\n== Demo: Agent scheduler ==")
    kernel = AgentKernel()

    def runner(agent_id: str, goal: str):
        return {"goal": goal, "status": "done"}

    kernel.scheduler.schedule("agent_a", "Goal A")
    kernel.scheduler.schedule("agent_b", "Goal B")
    started = kernel.scheduler.tick(runner)
    _print("Started tasks", [t.task_id for t in started])
    _print("Scheduler status", kernel.scheduler.status())
    assert kernel.scheduler.status()["completed"] == 2


def demo_syscalls() -> None:
    print("\n== Demo: Syscalls ==")
    kernel = AgentKernel()
    session = kernel.create_session(name="syscall-agent", roles=["developer"], model="mock")

    from syscalls import SyscallRequest, SyscallType, SyscallOp

    req = SyscallRequest(
        syscall_type=SyscallType.LLM,
        operation=SyscallOp.LLM_GENERATE,
        payload={"messages": [{"role": "user", "content": "hello"}]},
        agent_id=session.agent_id,
    )
    resp = kernel.syscall(req)
    _print("LLM syscall", resp.to_dict())
    assert resp.success

    req2 = SyscallRequest(
        syscall_type=SyscallType.STORAGE,
        operation=SyscallOp.STORAGE_SAVE,
        payload={"key": "syscall_test", "data": {"hello": "world"}},
        agent_id=session.agent_id,
    )
    resp2 = kernel.syscall(req2)
    _print("Storage syscall", resp2.to_dict())
    assert resp2.success


def demo_permission_denied() -> None:
    print("\n== Demo: Permission denied (guest) ==")
    kernel = AgentKernel()
    session = kernel.create_session(name="guest-agent", roles=["guest"], model="mock")

    from syscalls import SyscallRequest, SyscallType, SyscallOp

    req = SyscallRequest(
        syscall_type=SyscallType.TOOL,
        operation=SyscallOp.TOOL_CALL,
        payload={"name": "calculator", "args": {"expression": "1+1"}},
        agent_id=session.agent_id,
    )
    resp = kernel.syscall(req)
    _print("Tool syscall (guest)", resp.to_dict())
    assert not resp.success
    assert "Permission denied" in (resp.error or "")


def main() -> None:
    parser = argparse.ArgumentParser(description="UC-317 — AIOS-style Agent Kernel")
    parser.add_argument("--demo-basic-chat", action="store_true")
    parser.add_argument("--demo-tool-use", action="store_true")
    parser.add_argument("--demo-memory", action="store_true")
    parser.add_argument("--demo-storage", action="store_true")
    parser.add_argument("--demo-scheduler", action="store_true")
    parser.add_argument("--demo-syscalls", action="store_true")
    parser.add_argument("--demo-permission-denied", action="store_true")
    parser.add_argument("--demo-all", action="store_true")
    parser.add_argument("--server", action="store_true", help="Run Flask API server")
    args = parser.parse_args()

    if args.server:
        from api_317 import run_server
        run_server()
        return

    if args.demo_all or args.demo_basic_chat:
        demo_basic_chat()
    if args.demo_all or args.demo_tool_use:
        demo_tool_use()
    if args.demo_all or args.demo_memory:
        demo_memory()
    if args.demo_all or args.demo_storage:
        demo_storage()
    if args.demo_all or args.demo_scheduler:
        demo_scheduler()
    if args.demo_all or args.demo_syscalls:
        demo_syscalls()
    if args.demo_all or args.demo_permission_denied:
        demo_permission_denied()

    if not any([
        args.demo_all, args.demo_basic_chat, args.demo_tool_use, args.demo_memory,
        args.demo_storage, args.demo_scheduler, args.demo_syscalls,
        args.demo_permission_denied, args.server,
    ]):
        parser.print_help()


if __name__ == "__main__":
    main()
