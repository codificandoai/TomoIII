"""UC-317 — Agent Kernel: núcleo AIOS-style que conecta LLMs, tools, memoria y storage."""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from access_manager import AccessManager, Permission
from agent_scheduler import AgentScheduler
from kernel_config import KernelConfig
from llm_core import LLMCore
from memory_manager import MemoryManager
from storage_manager import StorageManager
from syscalls import SyscallRequest, SyscallResponse, SyscallOp
from tool_manager import ToolManager


@dataclass
class AgentSession:
    agent_id: str
    name: str
    roles: List[str] = field(default_factory=list)
    model: Optional[str] = None
    system_prompt: str = "You are a helpful AI agent."
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentKernel:
    """Kernel AIOS-style: punto único de acceso a recursos del agente."""

    def __init__(self, config: Optional[KernelConfig] = None) -> None:
        self.config = config or KernelConfig.default()
        self.llm = LLMCore(self.config)
        self.memory = MemoryManager()
        self.tools = ToolManager()
        self.storage = StorageManager()
        self.access = AccessManager()
        self.scheduler = AgentScheduler(max_concurrent=self.config.max_agents)
        self._sessions: Dict[str, AgentSession] = {}

    def create_session(
        self,
        name: str,
        roles: Optional[List[str]] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentSession:
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        session = AgentSession(
            agent_id=agent_id,
            name=name,
            roles=roles or ["user"],
            model=model or self.config.default_model,
            system_prompt=system_prompt or "You are a helpful AI agent.",
            metadata=metadata or {},
        )
        self._sessions[agent_id] = session
        return session

    def get_session(self, agent_id: str) -> Optional[AgentSession]:
        return self._sessions.get(agent_id)

    def syscall(self, request: SyscallRequest) -> SyscallResponse:
        """Punto de entrada tipo "system call" para agentes."""
        roles = self._sessions.get(request.agent_id, AgentSession(agent_id=request.agent_id, name="unknown")).roles

        op = request.operation
        payload = request.payload

        if op == SyscallOp.LLM_GENERATE:
            if not self.access.has_permission(roles, Permission.LLM_CALL):
                return SyscallResponse(False, error="Permission denied: llm:call")
            messages = payload.get("messages", [])
            tools = payload.get("tools")
            model = payload.get("model")
            response = self.llm.generate(messages, tools=tools, model=model)
            return SyscallResponse(True, result=response)

        if op == SyscallOp.MEMORY_ADD:
            if not self.access.has_permission(roles, Permission.MEMORY_WRITE):
                return SyscallResponse(False, error="Permission denied: memory:write")
            entry = self.memory.add(
                request.agent_id,
                payload["content"],
                role=payload.get("role", "assistant"),
                source=payload.get("source", "conversation"),
                metadata=payload.get("metadata"),
                long_term=payload.get("long_term", False),
            )
            return SyscallResponse(True, result=entry)

        if op == SyscallOp.MEMORY_RETRIEVE:
            if not self.access.has_permission(roles, Permission.MEMORY_READ):
                return SyscallResponse(False, error="Permission denied: memory:read")
            entries = self.memory.retrieve(request.agent_id, payload["query"], top_k=payload.get("top_k", 3))
            return SyscallResponse(True, result=entries)

        if op == SyscallOp.TOOL_CALL:
            if not self.access.has_permission(roles, Permission.TOOL_USE):
                return SyscallResponse(False, error="Permission denied: tool:use")
            result = self.tools.call(payload["name"], payload.get("args", {}))
            return SyscallResponse(result.get("success", False), result=result)

        if op == SyscallOp.STORAGE_SAVE:
            if not self.access.has_permission(roles, Permission.STORAGE_WRITE):
                return SyscallResponse(False, error="Permission denied: storage:write")
            self.storage.save(payload["key"], payload["data"])
            return SyscallResponse(True, result={"saved": payload["key"]})

        if op == SyscallOp.STORAGE_LOAD:
            if not self.access.has_permission(roles, Permission.STORAGE_READ):
                return SyscallResponse(False, error="Permission denied: storage:read")
            data = self.storage.load(payload["key"])
            return SyscallResponse(True, result=data)

        if op == SyscallOp.SCHEDULE_AGENT:
            if not self.access.has_permission(roles, Permission.AGENT_SCHEDULE):
                return SyscallResponse(False, error="Permission denied: agent:schedule")
            task = self.scheduler.schedule(request.agent_id, payload["goal"])
            return SyscallResponse(True, result=task)

        return SyscallResponse(False, error=f"Unknown operation: {op}")


    # -------------------------------------------------------------------
    # UC-324 Safe Shutdown wrappers (delegate to scheduler)
    # -------------------------------------------------------------------

    def stop_accepting_tasks(self, shutdown_id: str = "") -> Dict[str, Any]:
        """UC-324: stop accepting new agent tasks."""
        return self.scheduler.stop_accepting_tasks(shutdown_id)

    def drain_and_cancel(self, shutdown_id: str = "", timeout_seconds: float = 30.0) -> Dict[str, Any]:
        """UC-324: drain and cancel pending/running tasks."""
        return self.scheduler.drain_and_cancel(shutdown_id, timeout_seconds)

    def resume_accepting_tasks(self) -> Dict[str, Any]:
        """UC-324: resume accepting tasks after approved reactivation."""
        return self.scheduler.resume_accepting_tasks()

    def is_accepting_tasks(self) -> bool:
        """UC-324: whether the scheduler is accepting new tasks."""
        return self.scheduler.is_accepting_tasks

    def chat(self, agent_id: str, message: str, use_tools: bool = True) -> Dict[str, Any]:
        """Conveniencia: conversación con el agente usando el kernel."""
        session = self._sessions.get(agent_id)
        if not session:
            raise ValueError(f"Agent session {agent_id} not found")

        self.memory.add(agent_id, message, role="user", source="conversation")
        messages = [{"role": "system", "content": session.system_prompt}]
        messages.extend(self.memory.get_context(agent_id))

        tools = [self.tools._tools[t].to_openai() for t in self.tools._tools] if use_tools else None
        response = self.llm.generate(messages, tools=tools, model=session.model)

        # Ejecutar tool calls determinísticamente.
        tool_results = []
        for tc in response.tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", "{}")
            import json
            try:
                parsed = json.loads(args) if isinstance(args, str) else args
            except json.JSONDecodeError:
                parsed = {}
            res = self.tools.call(name, parsed)
            tool_results.append({"name": name, "result": res})
            self.memory.add(agent_id, f"Tool {name} result: {res}", role="system", source="tool")

        self.memory.add(agent_id, response.content, role="assistant", source="conversation")

        return {
            "agent_id": agent_id,
            "response": response.content,
            "model": response.model,
            "provider": response.provider,
            "tool_calls": response.tool_calls,
            "tool_results": tool_results,
            "usage": response.usage,
        }
