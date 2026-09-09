"""Tests para Extrinsic & Contextual Metrics en UC-703."""
from __future__ import annotations

import pytest

from fine_tuning.extrinsic_metrics.calculators import (
    ContextualRecallCalculator,
    ExtrinsicCalculator,
)
from fine_tuning.extrinsic_metrics.event_correlator import EventCorrelator
from fine_tuning.extrinsic_metrics.extrinsic_metrics_controller import (
    ExtrinsicMetricsController,
)
from fine_tuning.extrinsic_metrics.models_em import (
    ApplicationEvent,
    InferenceEvent,
    UnifiedSession,
)
from fine_tuning.extrinsic_metrics.observability import LokiLogger, PrometheusExporter


class TestEventCorrelator:
    def test_correlate_by_session_id(self):
        corr = EventCorrelator()
        corr.ingest_application_event(ApplicationEvent(session_id="s1", event_type="session_started"))
        corr.ingest_inference_event(InferenceEvent(trace_id="t1", session_id="s1"))
        session = corr.get_session("s1")
        assert session is not None
        assert "t1" in session.trace_ids

    def test_get_session_by_trace(self):
        corr = EventCorrelator()
        corr.ingest_inference_event(InferenceEvent(trace_id="t2", session_id="s2"))
        assert corr.get_session_by_trace("t2").session_id == "s2"


class TestExtrinsicCalculator:
    def test_task_success_and_cost(self):
        sessions = [
            UnifiedSession(
                session_id="s1",
                application_events=[
                    ApplicationEvent(session_id="s1", event_type="session_started", timestamp=0),
                    ApplicationEvent(session_id="s1", event_type="task_completed", timestamp=10, success=True),
                ],
                inference_events=[
                    InferenceEvent(trace_id="t1", session_id="s1", cost_usd=0.01),
                ],
            ),
            UnifiedSession(
                session_id="s2",
                application_events=[
                    ApplicationEvent(session_id="s2", event_type="session_started", timestamp=0),
                    ApplicationEvent(session_id="s2", event_type="user_abandoned", timestamp=5),
                ],
                inference_events=[
                    InferenceEvent(trace_id="t2", session_id="s2", cost_usd=0.005),
                ],
            ),
        ]
        calc = ExtrinsicCalculator()
        metrics = calc.calculate(sessions, 0, 20)
        assert metrics.total_sessions == 2
        assert metrics.completed_tasks == 1
        assert metrics.abandoned_tasks == 1
        assert metrics.task_success_rate == 0.5
        assert metrics.user_abandoned_rate == 0.5
        assert metrics.cost_per_completed_interaction_usd == 0.01

    def test_retention_lift(self):
        sessions = [
            UnifiedSession(
                session_id="s1",
                application_events=[
                    ApplicationEvent(session_id="s1", event_type="task_completed", success=True),
                ],
            ),
        ]
        calc = ExtrinsicCalculator()
        metrics = calc.calculate(sessions, 0, 10, baseline_retention_rate=40.0)
        assert metrics.retention_lift_pct is not None


class TestContextualRecallCalculator:
    def test_multi_turn_consistency(self):
        sessions = [
            UnifiedSession(
                session_id="s1",
                inference_events=[
                    InferenceEvent(trace_id="t1", session_id="s1", context_references=["doc1"]),
                    InferenceEvent(trace_id="t2", session_id="s1", context_references=["doc1", "doc2"]),
                ],
            ),
        ]
        calc = ContextualRecallCalculator()
        metrics = calc.calculate(sessions, 0, 10)
        assert metrics.multi_turn_consistency_score > 0
        assert metrics.sessions_with_context == 1

    def test_reference_correctness(self):
        sessions = [
            UnifiedSession(
                session_id="s1",
                application_events=[
                    ApplicationEvent(
                        session_id="s1",
                        event_type="task_completed",
                        metadata={"expected_references": ["doc1", "doc2"]},
                    ),
                ],
                inference_events=[
                    InferenceEvent(trace_id="t1", session_id="s1", context_references=["doc1"]),
                ],
            ),
        ]
        calc = ContextualRecallCalculator()
        metrics = calc.calculate(sessions, 0, 10)
        assert metrics.reference_correctness_score == 0.5


class TestObservability:
    def test_prometheus_render(self):
        exporter = PrometheusExporter()
        from fine_tuning.extrinsic_metrics.models_em import ExtrinsicMetrics
        exporter.emit_extrinsic(ExtrinsicMetrics(
            task_success_rate=0.9, user_abandoned_rate=0.05, total_sessions=10
        ))
        text = exporter.render()
        assert "llm_extrinsic_task_success_rate" in text
        assert "llm_extrinsic_total_sessions" in text

    def test_loki_logger(self):
        logger = LokiLogger()
        logger.log("test", "s1", "t1", "ingest", "ok")
        assert len(logger.get_entries()) == 1


class TestExtrinsicMetricsController:
    def test_full_flow(self):
        ctrl = ExtrinsicMetricsController()
        ctrl.ingest_application_event({
            "session_id": "s1",
            "event_type": "session_started",
            "timestamp": 0,
        })
        ctrl.ingest_application_event({
            "session_id": "s1",
            "event_type": "task_completed",
            "timestamp": 10,
            "success": True,
            "revenue_usd": 5.0,
        })
        ctrl.ingest_inference_event({
            "trace_id": "t1",
            "session_id": "s1",
            "tokens_input": 100,
            "tokens_output": 20,
            "latency_ms": 200.0,
            "cost_usd": 0.01,
            "context_chunks_used": 3,
            "context_references": ["doc1"],
            "llm_judge_context_score": 0.85,
        })
        snapshot = ctrl.compute_metrics(window_start=0, window_end=20)
        assert snapshot.extrinsic is not None
        assert snapshot.contextual is not None
        assert snapshot.extrinsic.completed_tasks == 1
        assert snapshot.extrinsic.revenue_per_session_usd == 5.0
        assert snapshot.contextual.avg_llm_judge_context_score == 0.85
        assert "llm_extrinsic_task_success_rate" in ctrl.render_prometheus()

    def test_compute_empty(self):
        ctrl = ExtrinsicMetricsController()
        snapshot = ctrl.compute_metrics(window_start=0, window_end=10)
        assert snapshot.extrinsic.total_sessions == 0


class TestExtrinsicMetricsAPIIntegration:
    @pytest.fixture
    def client(self):
        import api_703
        api_703._em_controller = None
        app = api_703.create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_ingest_app_event(self, client):
        resp = client.post("/api/v1/ft/extrinsic-metrics/app-event", json={
            "session_id": "api-s1",
            "event_type": "task_completed",
            "success": True,
        })
        assert resp.status_code == 201
        assert resp.get_json()["data"]["session_id"] == "api-s1"

    def test_ingest_inf_event(self, client):
        resp = client.post("/api/v1/ft/extrinsic-metrics/inf-event", json={
            "trace_id": "api-t1",
            "session_id": "api-s1",
            "cost_usd": 0.02,
            "context_chunks_used": 2,
        })
        assert resp.status_code == 201

    def test_compute_and_prometheus(self, client):
        client.post("/api/v1/ft/extrinsic-metrics/app-event", json={
            "session_id": "api-s2",
            "event_type": "session_started",
            "timestamp": 0,
        })
        client.post("/api/v1/ft/extrinsic-metrics/app-event", json={
            "session_id": "api-s2",
            "event_type": "task_completed",
            "timestamp": 10,
            "success": True,
        })
        client.post("/api/v1/ft/extrinsic-metrics/inf-event", json={
            "trace_id": "api-t2",
            "session_id": "api-s2",
            "cost_usd": 0.01,
            "llm_judge_context_score": 0.9,
        })
        resp = client.post("/api/v1/ft/extrinsic-metrics/compute", json={
            "window_start": 0,
            "window_end": 20,
        })
        assert resp.status_code == 200
        assert resp.get_json()["data"]["extrinsic"]["completed_tasks"] == 1
        prom = client.get("/api/v1/ft/extrinsic-metrics/prometheus")
        assert prom.status_code == 200
        assert "llm_extrinsic_task_success_rate" in prom.get_data(as_text=True)

    def test_session_endpoint(self, client):
        client.post("/api/v1/ft/extrinsic-metrics/app-event", json={
            "session_id": "api-s3",
            "event_type": "session_started",
        })
        resp = client.get("/api/v1/ft/extrinsic-metrics/sessions/api-s3")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["session_id"] == "api-s3"
