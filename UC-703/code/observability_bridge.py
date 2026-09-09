"""
UC-703 — Observability Bridge.

Envía métricas, trazas y logs al stack de observabilidad (UC-309 / Grafana).
Si UC-309 no está disponible, almacena eventos en buffer local exportable.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ObservabilityBridge:
    """
    Puente de observabilidad para UC-703.

    - Emite métricas simples counters/gauges en memoria.
    - Emite spans/logs al `event_sink` si se provee.
    - Si `event_sink` no está disponible, guarda eventos en buffer.
    """

    service_name: str = "uc703-agent-runtime"
    event_sink: Optional[Callable[[str, Dict[str, Any]], None]] = None
    _events: List[Dict[str, Any]] = field(default_factory=list)
    _counters: Dict[str, int] = field(default_factory=dict)
    _gauges: Dict[str, float] = field(default_factory=dict)
    _histograms: Dict[str, List[float]] = field(default_factory=dict)

    def _emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        event = {
            "type": event_type,
            "service": self.service_name,
            "trace_id": payload.get("trace_id") or f"trace-{uuid.uuid4().hex[:12]}",
            "timestamp": time.time(),
            "payload": payload,
        }
        self._events.append(event)
        if self.event_sink:
            try:
                self.event_sink(event_type, event)
            except Exception:
                pass

    def record_objective_created(self, objective_id: str, agent_id: str) -> None:
        self._counters["uc703_objectives_created_total"] = self._counters.get("uc703_objectives_created_total", 0) + 1
        self._emit("objective_created", {"objective_id": objective_id, "agent_id": agent_id})

    def record_plan_created(self, objective_id: str, plan_id: str, num_steps: int) -> None:
        self._counters["uc703_plans_created_total"] = self._counters.get("uc703_plans_created_total", 0) + 1
        self._gauges[f"uc703_plan_steps{{objective_id='{objective_id}'}}"] = num_steps
        self._emit("plan_created", {"objective_id": objective_id, "plan_id": plan_id, "num_steps": num_steps})

    def record_approval_requested(self, step_id: str, scope: str) -> None:
        key = f"uc703_approvals_requested_total{{scope='{scope}'}}"
        self._counters[key] = self._counters.get(key, 0) + 1
        self._emit("approval_requested", {"step_id": step_id, "scope": scope})

    def record_execution(self, step_id: str, backend: str, status: str, duration_seconds: float) -> None:
        self._counters["uc703_executions_total"] = self._counters.get("uc703_executions_total", 0) + 1
        key = f"uc703_executions_total{{backend='{backend}',status='{status}'}}"
        self._counters[key] = self._counters.get(key, 0) + 1
        self._histograms.setdefault(f"uc703_execution_duration_seconds{{backend='{backend}'}}", []).append(duration_seconds)
        self._emit("execution", {"step_id": step_id, "backend": backend, "status": status, "duration_seconds": duration_seconds})

    def record_task_status(self, task_id: str, status: str) -> None:
        self._gauges[f"uc703_task_status{{task_id='{task_id}',status='{status}'}}"] = 1.0
        self._emit("task_status", {"task_id": task_id, "status": status})

    def record_memory_sync(self, objective_id: str, operation: str) -> None:
        self._counters["uc703_memory_sync_total"] = self._counters.get("uc703_memory_sync_total", 0) + 1
        self._emit("memory_sync", {"objective_id": objective_id, "operation": operation})

    def get_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._events[-limit:]

    def render_prometheus_metrics(self) -> str:
        lines: List[str] = []
        for name, value in sorted(self._counters.items()):
            lines.append(f"# TYPE {name.split('{')[0]} counter")
            lines.append(f"{name} {value}")
        for name, value in sorted(self._gauges.items()):
            lines.append(f"# TYPE {name.split('{')[0]} gauge")
            lines.append(f"{name} {value}")
        return "\n".join(lines)

    def to_loki_lines(self) -> List[Dict[str, Any]]:
        return self._events
