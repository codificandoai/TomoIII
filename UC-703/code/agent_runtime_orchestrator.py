"""
UC-703 — Agent Runtime Orchestrator.

Orquesta el ciclo completo del agente AGI:
  pensar (UC-315/325) -> recordar (UC-326/296) -> decidir/aprobar (UC-290/300)
  -> ejecutar (Temporal / StackStorm / n8n / UC-317 local) -> observar.

Diseñado para tareas largas que sobreviven fallos, con checkpoints, pausa,
reanudación y cancelación.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from adapters.approval_gateway_adapter import ApprovalGatewayAdapter
from adapters.local_executor_adapter import LocalExecutorAdapter
from adapters.memory_sync_adapter import MemorySyncAdapter
from adapters.n8n_adapter import N8nAdapter
from adapters.stackstorm_runtime_adapter import StackStormRuntimeAdapter
from adapters.temporal_adapter import TemporalAdapter
from long_term_task_manager import LongTermTaskManager
from models_703 import (
    ApprovalDecision,
    Capability,
    ExecutionBackend,
    ExecutionResult,
    Objective,
    Plan,
    PlanStep,
    RuntimeTask,
    TaskStatus,
)
from observability_bridge import ObservabilityBridge
from resilience.recovery_orchestrator import RecoveryOrchestrator


class AgentRuntimeOrchestrator:
    """
    Runtime AGI unificado.

    Responsabilidades:
    1. Recibir objetivos y transformarlos en planes.
    2. Recuperar contexto de memoria (UC-326/296 vía adapter).
    3. Solicitar aprobación de pasos de ejecución (UC-290/300 vía adapter).
    4. Ejecutar pasos en el backend adecuado.
    5. Gestionar checkpoints y recuperación (LongTermTaskManager + Temporal).
    6. Sincronizar episodios con memoria del agente.
    7. Reportar observabilidad a UC-309/Grafana Stack.
    """

    def __init__(
        self,
        temporal: Optional[TemporalAdapter] = None,
        stackstorm: Optional[StackStormRuntimeAdapter] = None,
        n8n: Optional[N8nAdapter] = None,
        local: Optional[LocalExecutorAdapter] = None,
        approval_gateway: Optional[ApprovalGatewayAdapter] = None,
        memory_sync: Optional[MemorySyncAdapter] = None,
        task_manager: Optional[LongTermTaskManager] = None,
        observability: Optional[ObservabilityBridge] = None,
        planner: Optional[Callable[[Objective, List[Dict[str, Any]]], Plan]] = None,
        recovery_orchestrator: Optional[RecoveryOrchestrator] = None,
    ) -> None:
        self.temporal = temporal or TemporalAdapter()
        self.stackstorm = stackstorm or StackStormRuntimeAdapter()
        self.n8n = n8n or N8nAdapter()
        self.local = local or LocalExecutorAdapter()
        self.approval_gateway = approval_gateway or ApprovalGatewayAdapter()
        self.memory_sync = memory_sync or MemorySyncAdapter()
        self.task_manager = task_manager or LongTermTaskManager()
        self.observability = observability or ObservabilityBridge()
        self.planner = planner or self._default_planner
        self.recovery = recovery_orchestrator
        self._tasks: Dict[str, RuntimeTask] = {}

    # ------------------------------------------------------------------
    # Planner (default determinista; reemplazable por UC-315/325)
    # ------------------------------------------------------------------
    def _default_planner(self, objective: Objective, context: List[Dict[str, Any]]) -> Plan:
        """Planner mock: genera un plan simple basado en palabras clave."""
        desc = objective.description.lower()
        steps: List[PlanStep] = []
        if any(w in desc for w in ("investiga", "investigar", "buscar", "research")):
            steps.append(PlanStep(
                capability=Capability.REMEMBER,
                action="search_memory",
                params={"query": objective.description},
                reasoning="Recuperar conocimiento previo",
            ))
            steps.append(PlanStep(
                capability=Capability.EXECUTE_LOCAL,
                action="llm_call",
                params={"prompt": f"Analiza: {objective.description}", "context": [c.get("objective") for c in context[:3]]},
                reasoning="Generar análisis con LLM",
            ))
        elif any(w in desc for w in ("infra", "servidor", "servicio", "alerta", "disk", "cpu")):
            steps.append(PlanStep(
                capability=Capability.EXECUTE_STACKSTORM,
                action="remediate_disk_full",
                params={"path": "/", "service": "api"},
                reasoning="Remediar evento de infraestructura",
            ))
        elif any(w in desc for w in ("slack", "notion", "salesforce", "jira", "email")):
            wf = "notify_slack" if "slack" in desc else "send_email"
            steps.append(PlanStep(
                capability=Capability.EXECUTE_N8N,
                action=wf,
                params={"channel": "#ops", "message": objective.description},
                reasoning="Conectar con SaaS vía n8n",
            ))
        elif any(w in desc for w in ("largo", "días", "horas", "workflow")):
            steps.append(PlanStep(
                capability=Capability.EXECUTE_TEMPORAL,
                action="long_running_migration",
                params={"target": "aws", "estimated_duration_seconds": 7200},
                estimated_duration_seconds=7200,
                reasoning="Tarea de larga duración con checkpointing",
            ))
        else:
            steps.append(PlanStep(
                capability=Capability.EXECUTE_LOCAL,
                action="llm_call",
                params={"prompt": objective.description},
                reasoning="Respuesta directa",
            ))
        return Plan(
            objective_id=objective.objective_id,
            steps=steps,
            summary=f"Plan automático para {objective.description}",
            risk_level="low" if len(steps) == 1 else "medium",
        )

    # ------------------------------------------------------------------
    # Ciclo principal
    # ------------------------------------------------------------------
    def submit_objective(
        self,
        description: str,
        agent_id: str = "",
        tenant_id: str = "",
        requested_by: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> RuntimeTask:
        objective = Objective(
            description=description,
            agent_id=agent_id,
            tenant_id=tenant_id,
            requested_by=requested_by,
            context=context or {},
        )
        task = RuntimeTask(
            objective_id=objective.objective_id,
            objective=objective,
            status=TaskStatus.PENDING,
        )
        self._tasks[task.task_id] = task
        self.observability.record_objective_created(objective.objective_id, agent_id or "unknown")
        return task

    def plan_task(self, task_id: str) -> Optional[RuntimeTask]:
        task = self._tasks.get(task_id)
        if not task or not task.objective:
            return None
        task.status = TaskStatus.PLANNING
        context = self.memory_sync.read_context(task.objective.description)
        plan = self.planner(task.objective, context)
        task.plan = plan
        task.pending_steps = [s.step_id for s in plan.steps]
        task.status = TaskStatus.AWAITING_APPROVAL
        self.observability.record_plan_created(
            task.objective_id, plan.plan_id, len(plan.steps)
        )
        return task

    def approve_all_steps(self, task_id: str) -> Optional[RuntimeTask]:
        task = self._tasks.get(task_id)
        if not task or not task.plan:
            return None
        for step in task.plan.steps:
            decision = self.approval_gateway.request_approval(
                action=step.action,
                params=step.params,
                scope="auto",
                requested_by=task.objective.requested_by if task.objective else "runtime",
            )
            task.approvals[step.step_id] = decision
            self.observability.record_approval_requested(step.step_id, decision.scope)
        task.status = TaskStatus.APPROVED
        return task

    def approve_step(self, task_id: str, step_id: str, scope: str = "auto") -> Optional[ApprovalDecision]:
        task = self._tasks.get(task_id)
        if not task or not task.plan:
            return None
        step = next((s for s in task.plan.steps if s.step_id == step_id), None)
        if not step:
            return None
        decision = self.approval_gateway.request_approval(
            action=step.action,
            params=step.params,
            scope=scope,
        )
        task.approvals[step_id] = decision
        self.observability.record_approval_requested(step_id, decision.scope)
        return decision

    def execute_task(self, task_id: str) -> Optional[RuntimeTask]:
        task = self._tasks.get(task_id)
        if not task or not task.plan:
            return None
        task.status = TaskStatus.RUNNING
        self.observability.record_task_status(task_id, task.status.value)

        # Crear tarea durable
        durable = self.task_manager.create_task(
            task.objective_id, timeout_seconds=86400.0
        )
        self.task_manager.start_task(durable.task_id)

        for step in task.plan.steps:
            if task.status == TaskStatus.CANCELLED:
                break
            decision = task.approvals.get(step.step_id)
            if not decision or decision.decision != "allowed":
                result = ExecutionResult(
                    step_id=step.step_id,
                    status="denied",
                    error="Step not approved or denied",
                    backend="none",
                )
            else:
                started = time.time()
                result = self._execute_step(step, decision)
                duration = time.time() - started
                self.observability.record_execution(
                    step.step_id, result.backend, result.status, duration
                )
                self.memory_sync.update_working_memory(
                    task.objective_id, {step.step_id: result.to_dict()}
                )
                self.task_manager.save_checkpoint(
                    durable.task_id,
                    step.step_id,
                    {"result": result.to_dict(), "completed_steps": task.completed_steps},
                )
            # Resilient recovery layer: try to recover from step failures
            if result.status != "succeeded" and self.recovery is not None:
                recovery_report = self.recovery.invoke(
                    run_id=task.objective_id,
                    step_id=step.step_id,
                    tool_name=step.action,
                    fn=lambda **kwargs: self._execute_step(step, decision),
                    params=step.params,
                    completed_steps=list(task.completed_steps),
                    partial_state={sid: r.to_dict() for sid, r in task.results.items()},
                )
                if recovery_report.final_status in ("succeeded", "recovered"):
                    result.status = "succeeded"
                    result.output = recovery_report.final_output
                    result.error = ""
                    result.backend = "recovery"
                elif recovery_report.final_status == "escalated":
                    result.status = "escalated"
                    result.error = f"escalated to HITL ({recovery_report.recovery_action})"
                    result.backend = "recovery"
            task.results[step.step_id] = result
            if step.step_id in task.pending_steps:
                task.pending_steps.remove(step.step_id)
            if result.status == "succeeded":
                task.completed_steps.append(step.step_id)
            else:
                task.failed_steps.append(step.step_id)
                task.status = TaskStatus.FAILED
                break

        if task.status == TaskStatus.RUNNING:
            task.status = TaskStatus.COMPLETED
        self.task_manager.complete_task(durable.task_id)
        self.observability.record_task_status(task_id, task.status.value)
        self.memory_sync.write_episode(
            objective_id=task.objective_id,
            objective=task.objective.description,
            outcome=task.status.value,
            metadata={
                "completed_steps": task.completed_steps,
                "failed_steps": task.failed_steps,
                "plan_id": task.plan.plan_id,
            },
        )
        task.updated_at = time.time()
        return task

    def _execute_step(self, step: PlanStep, decision: ApprovalDecision) -> ExecutionResult:
        backend = self._select_backend(step.capability)
        result = ExecutionResult(
            step_id=step.step_id,
            backend=backend.value,
            trace_id=decision.approval_ref,
        )
        if backend == ExecutionBackend.TEMPORAL:
            wf = self.temporal.start_workflow(
                activities=[{"name": step.action, "params": step.params}],
                context={"approval_ref": decision.approval_ref},
            )
            self.temporal.run_workflow(wf.workflow_id)
            updated = self.temporal.get_workflow(wf.workflow_id)
            if updated and updated.activities:
                act = updated.activities[0]
                result.status = "succeeded" if act.status == "completed" else "failed"
                result.output = act.result or {}
                result.error = act.error
            else:
                result.status = "failed"
                result.error = "Temporal workflow returned no activity"
        elif backend == ExecutionBackend.STACKSTORM:
            exec_ = self.stackstorm.execute(
                playbook=step.action,
                params=step.params,
                approval_ref=decision.approval_ref,
            )
            result.status = "succeeded" if exec_.status == "succeeded" else "failed"
            result.output = exec_.result or {}
            result.error = exec_.error
        elif backend == ExecutionBackend.N8N:
            exec_ = self.n8n.execute(
                workflow_id=step.action,
                payload=step.params,
                approval_ref=decision.approval_ref,
            )
            result.status = "succeeded" if exec_.status == "succeeded" else "failed"
            result.output = exec_.result or {}
            result.error = exec_.error
        else:
            exec_ = self.local.execute(
                action=step.action,
                params=step.params,
                approval_ref=decision.approval_ref,
            )
            result.status = "succeeded" if exec_.status == "succeeded" else "failed"
            result.output = exec_.result or {}
            result.error = exec_.error
        return result

    def _select_backend(self, capability: Capability) -> ExecutionBackend:
        mapping = {
            Capability.EXECUTE_TEMPORAL: ExecutionBackend.TEMPORAL,
            Capability.EXECUTE_STACKSTORM: ExecutionBackend.STACKSTORM,
            Capability.EXECUTE_N8N: ExecutionBackend.N8N,
            Capability.EXECUTE_LOCAL: ExecutionBackend.LOCAL,
            Capability.REMEMBER: ExecutionBackend.LOCAL,
            Capability.THINK: ExecutionBackend.LOCAL,
            Capability.APPROVE: ExecutionBackend.LOCAL,
        }
        return mapping.get(capability, ExecutionBackend.LOCAL)

    # ------------------------------------------------------------------
    # Control de tareas largas
    # ------------------------------------------------------------------
    def pause_task(self, task_id: str) -> Optional[RuntimeTask]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        task.status = TaskStatus.PAUSED
        self.observability.record_task_status(task_id, task.status.value)
        return task

    def resume_task(self, task_id: str) -> Optional[RuntimeTask]:
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.PAUSED:
            return None
        task.status = TaskStatus.RUNNING
        self.observability.record_task_status(task_id, task.status.value)
        return task

    def cancel_task(self, task_id: str) -> Optional[RuntimeTask]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        task.status = TaskStatus.CANCELLED
        self.observability.record_task_status(task_id, task.status.value)
        return task

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def get_task(self, task_id: str) -> Optional[RuntimeTask]:
        return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[str] = None) -> List[RuntimeTask]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status.value == status]
        return tasks

    def runtime_status(self) -> Dict[str, Any]:
        return {
            "tasks_total": len(self._tasks),
            "by_status": self._count_by_status(),
            "observability_events": len(self.observability.get_events()),
            "temporal_workflows": len(self.temporal._workflows),
            "stackstorm_executions": len(self.stackstorm._executions),
            "n8n_executions": len(self.n8n._executions),
            "memory_episodes": len(self.memory_sync._episodes),
        }

    def _count_by_status(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for task in self._tasks.values():
            counts[task.status.value] = counts.get(task.status.value, 0) + 1
        return counts
