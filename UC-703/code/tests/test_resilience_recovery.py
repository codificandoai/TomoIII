"""Tests para Resilient Multi-Step Tool Recovery Layer en UC-703."""
from __future__ import annotations

import pytest

from resilience.error_classifier import ErrorClassifier
from resilience.escalation_chain import EscalationChain, HITLQueue, RepairAgent
from resilience.models_resilience import RetryPolicy
from resilience.recovery_orchestrator import RecoveryOrchestrator
from resilience.replanning import ContextRebuilder, ReplanningAgent
from resilience.retry_manager import RetryManager
from resilience.schema_validator import SchemaValidator
from resilience.telemetry_exporter import RecoveryTelemetryExporter


class TestSchemaValidator:
    def test_valid_input(self):
        v = SchemaValidator()
        v.register_tool("t1", input_schema={"required": ["x"], "types": {"x": "int"}})
        res = v.validate_input("t1", {"x": 1})
        assert res["valid"]

    def test_missing_required(self):
        v = SchemaValidator()
        v.register_tool("t1", input_schema={"required": ["x"]})
        res = v.validate_input("t1", {})
        assert not res["valid"]

    def test_forbidden_field(self):
        v = SchemaValidator()
        v.register_tool("t1", input_schema={"forbidden": ["secret"]})
        res = v.validate_input("t1", {"secret": "x"})
        assert not res["valid"]


class TestErrorClassifier:
    def test_timeout(self):
        c = ErrorClassifier()
        cls = c.classify(error_message="connection timeout")
        assert cls.category == "timeout"
        assert cls.retryable

    def test_context_limit(self):
        c = ErrorClassifier()
        cls = c.classify(error_message="context length limit exceeded")
        assert cls.category == "context_limit"
        assert not cls.retryable

    def test_auth(self):
        c = ErrorClassifier()
        cls = c.classify(error_message="unauthorized permission denied")
        assert cls.category == "auth"
        assert cls.severity == "critical"


class TestRetryManager:
    def test_success(self):
        rm = RetryManager(RetryPolicy(base_delay_seconds=0, max_delay_seconds=0))
        result = rm.execute("s1", "t1", lambda: 42)
        assert result.status == "succeeded"
        assert result.output == 42
        assert result.attempts == 1

    def test_retry_then_fail(self):
        rm = RetryManager(RetryPolicy(max_retries=2, base_delay_seconds=0, max_delay_seconds=0))
        result = rm.execute("s1", "t1", lambda: (_ for _ in ()).throw(TimeoutError("timeout")))
        assert result.status == "failed"
        assert result.attempts == 3
        assert result.error_category == "timeout"

    def test_backoff_jitter(self):
        rm = RetryManager(RetryPolicy(base_delay_seconds=0.01, max_delay_seconds=0.1, jitter=True))
        # Just check computation is positive
        delay = rm._compute_delay(1)
        assert delay > 0


class TestReplanning:
    def test_build_context(self):
        cr = ContextRebuilder()
        from resilience.models_resilience import ErrorClassification
        state = cr.build_context(
            run_id="r1",
            completed_steps=["s0"],
            failed_step="s1",
            partial_state={"x": 1},
            classification=ErrorClassification(category="timeout", retryable=True, root_cause_hint="timeout"),
            tool_name="tool1",
            error_message="timeout",
        )
        assert state.completed_steps == ["s0"]
        assert "timeout" in state.fallback_prompt

    def test_suggest_alternative(self):
        cr = ContextRebuilder()
        from resilience.models_resilience import ErrorClassification
        state = cr.build_context(
            run_id="r1",
            completed_steps=["s0"],
            failed_step="s1",
            partial_state={},
            classification=ErrorClassification(category="timeout", retryable=True, root_cause_hint="timeout"),
            tool_name="tool1",
            error_message="timeout",
        )
        agent = ReplanningAgent()
        suggestion = agent.suggest(state, ["tool1", "tool2"])
        assert suggestion.strategy == "alternative_tool"


class TestEscalationChain:
    def test_repair_success(self):
        ec = EscalationChain()
        from resilience.models_resilience import ResilientPlanState
        state = ResilientPlanState(run_id="r1", failed_step="s1")
        result = ec.escalate(state, "tool1", lambda verbose=True, retries=3: {"ok": True})
        assert result.status == "recovered"

    def test_hitl_after_repair_fails(self):
        ec = EscalationChain()
        from resilience.models_resilience import ResilientPlanState
        state = ResilientPlanState(run_id="r1", failed_step="s1")
        result = ec.escalate(state, "tool1", lambda: (_ for _ in ()).throw(Exception("fail")))
        assert result.status == "escalated"

    def test_hitl_decide(self):
        q = HITLQueue()
        from resilience.models_resilience import ResilientPlanState
        state = ResilientPlanState(run_id="r1", failed_step="s1")
        rec = q.request_review("s1", state.to_dict())
        q.decide(rec.escalation_id, "continue")
        assert rec.status == "resolved"


class TestRecoveryTelemetryExporter:
    def test_metrics(self):
        exporter = RecoveryTelemetryExporter()
        from resilience.models_resilience import ToolResult
        exporter.record_tool_result(ToolResult(status="failed", error_category="timeout", attempts=3, backend="t1"))
        text = exporter.render_prometheus()
        assert "llm_recovery_errors_total" in text
        assert "llm_recovery_attempts" in text


class TestRecoveryOrchestrator:
    def test_successful_invocation(self):
        ro = RecoveryOrchestrator(retry_manager=RetryManager(RetryPolicy(base_delay_seconds=0, max_delay_seconds=0)))
        report = ro.invoke("r1", "s1", "tool1", lambda expected_value: {"result": expected_value}, {"expected_value": 42})
        assert report.final_status == "succeeded"

    def test_input_schema_failure(self):
        ro = RecoveryOrchestrator()
        ro.register_tool("tool1", input_schema={"required": ["expected_value"]})
        report = ro.invoke("r1", "s1", "tool1", lambda expected_value: {"result": expected_value}, {})
        assert report.final_status == "failed"
        assert "schema validation failed" in report.original_error

    def test_timeout_then_escalation(self):
        ro = RecoveryOrchestrator(retry_manager=RetryManager(RetryPolicy(max_retries=1, base_delay_seconds=0, max_delay_seconds=0)))
        report = ro.invoke("r1", "s1", "tool1", lambda: (_ for _ in ()).throw(TimeoutError("timeout")), {})
        assert report.final_status == "escalated"
        assert report.replan_suggestion is not None

    def test_retry_success_after_failures(self):
        calls = {"count": 0}
        def flaky(**kwargs):
            calls["count"] += 1
            if calls["count"] < 3:
                raise TimeoutError("timeout")
            return {"ok": True}
        ro = RecoveryOrchestrator(retry_manager=RetryManager(RetryPolicy(max_retries=3, base_delay_seconds=0, max_delay_seconds=0)))
        report = ro.invoke("r1", "s1", "tool1", flaky, {})
        assert report.final_status == "succeeded"
        assert report.attempts == 3


class TestRecoveryAPIIntegration:
    @pytest.fixture
    def client(self):
        import api_703
        from resilience.models_resilience import RetryPolicy
        from resilience.retry_manager import RetryManager
        api_703._recovery_controller = RecoveryOrchestrator(
            retry_manager=RetryManager(RetryPolicy(base_delay_seconds=0.0, max_delay_seconds=0.0))
        )
        app = api_703.create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_register_tool(self, client):
        resp = client.post("/api/v1/runtime/recovery/register-tool", json={
            "tool_name": "api-tool",
            "input_schema": {"required": ["x"]},
        })
        assert resp.status_code == 201

    def test_invoke_success(self, client):
        resp = client.post("/api/v1/runtime/recovery/invoke", json={
            "run_id": "r-api",
            "step_id": "s1",
            "tool_name": "api-tool2",
            "params": {"expected_value": "hello"},
        })
        assert resp.status_code == 200
        assert resp.get_json()["data"]["final_status"] == "succeeded"

    def test_invoke_timeout_escalation(self, client):
        resp = client.post("/api/v1/runtime/recovery/invoke", json={
            "run_id": "r-api",
            "step_id": "s1",
            "tool_name": "api-tool3",
            "params": {},
        })
        assert resp.status_code == 200
        assert resp.get_json()["data"]["final_status"] == "escalated"

    def test_prometheus_and_logs(self, client):
        client.post("/api/v1/runtime/recovery/invoke", json={
            "run_id": "r-api-prometheus",
            "step_id": "s1",
            "tool_name": "api-tool4",
            "params": {},
        })
        prom = client.get("/api/v1/runtime/recovery/prometheus")
        assert prom.status_code == 200
        assert "llm_recovery" in prom.get_data(as_text=True)
        logs = client.get("/api/v1/runtime/recovery/logs")
        assert logs.status_code == 200
        assert isinstance(logs.get_json()["data"], list)
