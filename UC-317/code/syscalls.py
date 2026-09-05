"""UC-317 — Syscalls: abstracción de operaciones del kernel para agentes."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class SyscallType(str, Enum):
    LLM = "llm"
    MEMORY = "memory"
    TOOL = "tool"
    STORAGE = "storage"
    SCHEDULE = "schedule"


class SyscallOp(str, Enum):
    LLM_GENERATE = "llm.generate"
    MEMORY_ADD = "memory.add"
    MEMORY_RETRIEVE = "memory.retrieve"
    TOOL_CALL = "tool.call"
    STORAGE_SAVE = "storage.save"
    STORAGE_LOAD = "storage.load"
    SCHEDULE_AGENT = "schedule.agent"


@dataclass
class SyscallRequest:
    syscall_type: SyscallType
    operation: str
    payload: Dict[str, Any]
    agent_id: str
    trace_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "syscall_type": self.syscall_type.value,
            "operation": self.operation,
            "payload": self.payload,
            "agent_id": self.agent_id,
            "trace_id": self.trace_id,
        }


@dataclass
class SyscallResponse:
    success: bool
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }


class SyscallError(Exception):
    pass
