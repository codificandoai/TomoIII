"""Tests unitarios e integración para UC-703 AGI Agent Runtime."""
from __future__ import annotations

import pytest

from agent_runtime_orchestrator import AgentRuntimeOrchestrator
from adapters.approval_gateway_adapter import ApprovalGatewayAdapter
from adapters.local_executor_adapter import LocalExecutorAdapter
from adapters.memory_sync_adapter import MemorySyncAdapter
from adapters.n8n_adapter import N8nAdapter
from adapters.stackstorm_runtime_adapter import StackStormRuntimeAdapter
from adapters.temporal_adapter import TemporalAdapter
from long_term_task_manager import LongTermTaskManager
from models_703 import Capability, ExecutionBackend, PlanStep, TaskStatus
from observability_bridge import ObservabilityBridge


class TestTemporalAdapter:
    def test_workflow_lifecycle(self):
        adapter = TemporalAdapter()
        adapter.register_activity("add", lambda x, y: x + y)
        wf = adapter.start_workflow(
            activities=[{"name": "add", "params": {"x": 1, "y": 2}}],
        )
        result = adapter.run_workflow(wf.workflow_id)
        assert result is not None
        assert result.status == "completed"
        assert result.activities[0].result == 3

    def test_signal_cancel(self):
        adapter = TemporalAdapter()
        wf = adapter.start_workflow(activities=[])
        adapter.signal_workflow(wf.workflow_id, "cancel")
        updated = adapter.get_workflow(wf.workflow_id)
        assert updated.status == "cancelled"

    def test_retry_on_failure(self):
        adapter = TemporalAdapter()
        adapter.register_activity("fail", lambda: (_ for _ in ()).throw(ValueError("boom")))
        wf = adapter.start_workflow(activities=[{"name": "fail", "params": {}, "max_attempts": 2}])
        result = adapter.run_workflow(wf.workflow_id)
        assert result.status == "failed"
        assert result.activities[0].attempt == 2


class TestStackStormRuntimeAdapter:
    def test_execute_allowed(self):
        st2 = StackStormRuntimeAdapter()
        exec_ = st2.execute("remediate_disk_full", {"path": "/"}, "aprv-1")
        assert exec_.status == "succeeded"

    def test_missing_approval(self):
        st2 = StackStormRuntimeAdapter()
        exec_ = st2.execute("remediate_disk_full", {}, "")
        assert exec_.status == "failed"
        assert "approval_ref" in exec_.error

    def test_playbook_not_allowed(self):
        st2 = StackStormRuntimeAdapter()
        exec_ = st2.execute("unknown_playbook", {}, "aprv-1")
        assert exec_.status == "failed"


class TestN8nAdapter:
    def test_execute_allowed(self):
        n8n = N8nAdapter()
        exec_ = n8n.execute("notify_slack", {"channel": "#ops"}, "aprv-1")
        assert exec_.status == "succeeded"

    def test_missing_approval(self):
        n8n = N8nAdapter()
        exec_ = n8n.execute("notify_slack", {}, "")
        assert exec_.status == "failed"

    def test_workflow_not_allowed(self):
        n8n = N8nAdapter()
        exec_ = n8n.execute("malicious", {}, "aprv-1")
        assert exec_.status == "failed"


class TestApprovalGatewayAdapter:
    def test_auto_approval_low_risk(self):
        gw = ApprovalGatewayAdapter()
        decision = gw.request_approval("notify_team", {}, scope="auto")
        assert decision.decision == "allowed"

    def test_hitl_required_for_destructive(self):
        gw = ApprovalGatewayAdapter()
        decision = gw.request_approval("delete_resource", {}, scope="auto")
        assert decision.decision == "denied"

    def test_hitl_allowed_with_scope(self):
        gw = ApprovalGatewayAdapter()
        decision = gw.request_approval("delete_resource", {}, scope="hitl")
        assert decision.decision == "allowed"

    def test_high_cost_requires_hitl(self):
        gw = ApprovalGatewayAdapter()
        decision = gw.request_approval("run_job", {"estimated_cost_usd": 2000}, scope="auto")
        assert decision.decision == "denied"


class TestMemorySyncAdapter:
    def test_write_and_read(self):
        mem = MemorySyncAdapter()
        mem.write_episode("obj-1", "test", "completed", {"x": 1})
        ctx = mem.read_context("test objective")
        assert any(e["objective_id"] == "obj-1" for e in ctx)


class TestLongTermTaskManager:
    def test_checkpoint_recovery(self):
        tm = LongTermTaskManager()
        task = tm.create_task("obj-1")
        tm.start_task(task.task_id)
        tm.save_checkpoint(task.task_id, "step-1", {"x": 1})
        recovered = tm.recover_from_last_checkpoint(task.task_id)
        assert recovered is not None
        assert recovered.step_id == "step-1"

    def test_timeout(self):
        tm = LongTermTaskManager()
        task = tm.create_task("obj-1", timeout_seconds=0)
        assert tm.is_timed_out(task.task_id)


class TestAgentRuntimeOrchestrator:
    def test_research_objective_flow(self):
        orch = AgentRuntimeOrchestrator()
        task = orch.submit_objective("Investigar tendencias de mercado en Latam")
        orch.plan_task(task.task_id)
        orch.approve_all_steps(task.task_id)
        final = orch.execute_task(task.task_id)
        assert final is not None
        assert final.status == TaskStatus.COMPLETED

    def test_infra_objective_uses_stackstorm(self):
        orch = AgentRuntimeOrchestrator()
        task = orch.submit_objective("Remediar disco lleno en servidor prod")
        orch.plan_task(task.task_id)
        orch.approve_all_steps(task.task_id)
        final = orch.execute_task(task.task_id)
        assert final is not None
        step = final.plan.steps[0]
        assert step.capability == Capability.EXECUTE_STACKSTORM
        assert final.results[step.step_id].backend == ExecutionBackend.STACKSTORM.value

    def test_saas_objective_uses_n8n(self):
        orch = AgentRuntimeOrchestrator()
        task = orch.submit_objective("Enviar resumen a Slack")
        orch.plan_task(task.task_id)
        orch.approve_all_steps(task.task_id)
        final = orch.execute_task(task.task_id)
        assert final is not None
        step = final.plan.steps[0]
        assert step.capability == Capability.EXECUTE_N8N

    def test_long_running_uses_temporal(self):
        orch = AgentRuntimeOrchestrator()
        task = orch.submit_objective("Migrar base de datos AWS (tarea de 2 horas)")
        orch.plan_task(task.task_id)
        orch.approve_all_steps(task.task_id)
        final = orch.execute_task(task.task_id)
        assert final is not None
        step = final.plan.steps[0]
        assert step.capability == Capability.EXECUTE_TEMPORAL

    def test_destructive_step_requires_hitl(self):
        orch = AgentRuntimeOrchestrator()
        orch.approval_gateway.hitl_allowlist = ["destroy_database"]
        orch.approval_gateway.auto_allowlist = []

        # Custom planner to force a destructive step
        def planner(obj, ctx):
            from models_703 import Plan, PlanStep, Capability
            return Plan(
                objective_id=obj.objective_id,
                steps=[PlanStep(
                    capability=Capability.EXECUTE_LOCAL,
                    action="destroy_database",
                    params={"name": "prod-db"},
                )],
            )

        orch.planner = planner
        task = orch.submit_objective("Destruir base de datos")
        orch.plan_task(task.task_id)
        orch.approve_all_steps(task.task_id)  # auto scope => denied
        final = orch.execute_task(task.task_id)
        assert final.status == TaskStatus.FAILED

    def test_pause_and_resume(self):
        orch = AgentRuntimeOrchestrator()
        task = orch.submit_objective("Investigar tendencias")
        orch.pause_task(task.task_id)
        assert orch.get_task(task.task_id).status == TaskStatus.PAUSED
        orch.resume_task(task.task_id)
        assert orch.get_task(task.task_id).status == TaskStatus.RUNNING

    def test_runtime_status(self):
        orch = AgentRuntimeOrchestrator()
        orch.submit_objective("x")
        status = orch.runtime_status()
        assert status["tasks_total"] >= 1


class TestObservabilityBridge:
    def test_metrics_render(self):
        obs = ObservabilityBridge()
        obs.record_objective_created("obj-1", "agent-1")
        metrics = obs.render_prometheus_metrics()
        assert "uc703_objectives_created_total" in metrics


try:
    from api_703 import create_app
    from flask.testing import FlaskClient

    class TestAPI:
        @pytest.fixture
        def client(self):
            app = create_app(AgentRuntimeOrchestrator())
            app.config["TESTING"] = True
            with app.test_client() as c:
                yield c

        def test_health(self, client: FlaskClient):
            resp = client.get("/health")
            assert resp.status_code == 200
            assert resp.get_json()["status"] == "ok"

        def test_cards(self, client: FlaskClient):
            resp = client.get("/api/v1/cards")
            data = resp.get_json()["data"]
            assert "input" in data and "output" in data

        def test_create_objective(self, client: FlaskClient):
            resp = client.post("/api/v1/objective", json={"description": "test objective"})
            assert resp.status_code == 201
            data = resp.get_json()["data"]
            assert data["objective"]["description"] == "test objective"
            task_id = data["task_id"]

            resp = client.post(f"/api/v1/objective/{task_id}/plan")
            assert resp.status_code == 200

            resp = client.post(f"/api/v1/objective/{task_id}/approve")
            assert resp.status_code == 200

            resp = client.post(f"/api/v1/objective/{task_id}/execute")
            assert resp.status_code == 200
            executed = resp.get_json()["data"]
            assert executed["status"] in ("completed", "failed")

        def test_temporal_workflow_endpoints(self, client: FlaskClient):
            resp = client.post("/api/v1/temporal/workflow", json={
                "activities": [{"name": "add", "params": {"x": 1, "y": 2}}],
            })
            assert resp.status_code == 201
            wf_id = resp.get_json()["data"]["workflow_id"]
            resp = client.post(f"/api/v1/temporal/workflow/{wf_id}/run")
            assert resp.status_code == 200
            data = resp.get_json()["data"]
            assert data["status"] == "completed"

        def test_stackstorm_endpoint(self, client: FlaskClient):
            resp = client.post("/api/v1/stackstorm/execute", json={
                "playbook": "remediate_disk_full",
                "params": {"path": "/"},
                "approval_ref": "aprv-1",
            })
            assert resp.status_code == 200
            assert resp.get_json()["data"]["status"] == "succeeded"

        def test_n8n_endpoint(self, client: FlaskClient):
            resp = client.post("/api/v1/n8n/execute", json={
                "workflow_id": "notify_slack",
                "payload": {"channel": "#ops"},
                "approval_ref": "aprv-1",
            })
            assert resp.status_code == 200
            assert resp.get_json()["data"]["status"] == "succeeded"

except Exception:
    pass
