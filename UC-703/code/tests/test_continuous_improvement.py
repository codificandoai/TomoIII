"""Tests para Continuous Improvement & Feedback Loop Layer."""
from __future__ import annotations

import pytest

from continuous_improvement.continuous_improvement_controller import ContinuousImprovementController
from continuous_improvement.feedback_collector import FeedbackCollector
from continuous_improvement.models_ci import ExecutionLogRef, IncidentRef
from continuous_improvement.pattern_analyzer import PatternAnalyzer
from continuous_improvement.root_cause_analyzer import RootCauseAnalyzer
from continuous_improvement.improvement_recommender import ImprovementRecommender
from continuous_improvement.effectiveness_tracker import EffectivenessTracker


class TestFeedbackCollector:
    def test_collect_and_query(self):
        fc = FeedbackCollector()
        fb = fc.collect({
            "source": "explicit_rating",
            "category": "hallucination",
            "severity": "high",
            "model_version": "m1",
            "message": "The model cited a non-existent source.",
        })
        assert fb.feedback_id
        assert len(fc.query(category="hallucination")) == 1


class TestPatternAnalyzer:
    def test_systemic_cluster(self):
        fc = FeedbackCollector()
        for _ in range(4):
            fc.collect({
                "source": "complaint",
                "category": "hallucination",
                "severity": "high",
                "model_version": "m1",
                "prompt_version_id": "pv1",
            })
        analyzer = PatternAnalyzer(systemic_threshold=3)
        clusters = analyzer.analyze(fc.list_all())
        assert any(c.systemic and c.dominant_category == "hallucination" for c in clusters)

    def test_logs_enrich_cluster(self):
        analyzer = PatternAnalyzer(systemic_threshold=2)
        items = []
        logs = [
            ExecutionLogRef(log_id="l1", tool_name="rag_retriever", step_id="s1", run_id="r1", status="failed", error_category="timeout"),
            ExecutionLogRef(log_id="l2", tool_name="rag_retriever", step_id="s2", run_id="r2", status="failed", error_category="timeout"),
        ]
        clusters = analyzer.analyze(items, log_refs=logs)
        assert any(c.systemic for c in clusters)


class TestRootCauseAnalyzer:
    def test_prompt_cause(self):
        from continuous_improvement.models_ci import FeedbackCluster
        cluster = FeedbackCluster(pattern="prompt tone mismatch", feedback_ids=["f1"], dominant_category="quality")
        hypotheses = RootCauseAnalyzer().analyze(cluster)
        assert hypotheses[0].cause_category in ("prompt", "unknown")

    def test_data_cause(self):
        from continuous_improvement.models_ci import FeedbackCluster
        cluster = FeedbackCluster(pattern="rag document wrong source", feedback_ids=["f1"], dominant_category="hallucination")
        hypotheses = RootCauseAnalyzer().analyze(cluster)
        top = hypotheses[0]
        assert top.cause_category == "data_knowledge"


class TestImprovementRecommender:
    def test_recommend_data_curation(self):
        from continuous_improvement.models_ci import FeedbackCluster, RootCauseHypothesis
        cluster = FeedbackCluster(cluster_id="c1", pattern="rag issue", count=3, systemic=True, dominant_category="hallucination")
        hypothesis = RootCauseHypothesis(cluster_id="c1", cause_category="data_knowledge", confidence=0.9)
        recs = ImprovementRecommender().recommend(cluster, [hypothesis])
        assert any(r.action_type == "data_curation" for r in recs)


class TestEffectivenessTracker:
    def test_measure(self):
        et = EffectivenessTracker()
        et.register_baseline("hallucination_rate", 0.1)
        m = et.measure("rec-1", "hallucination_rate", 0.05)
        assert m.improvement_pct == 50.0


class TestContinuousImprovementController:
    def test_full_loop(self):
        ctrl = ContinuousImprovementController()
        for _ in range(4):
            ctrl.ingest_feedback({
                "source": "complaint",
                "category": "hallucination",
                "severity": "high",
                "model_version": "m1",
                "prompt_version_id": "pv1",
                "message": "Model made up a fact from document X",
            })
        result = ctrl.run_analysis()
        assert result["systemic_clusters"] >= 1
        assert result["recommendations_created"] >= 1

        pending = ctrl.get_pending_recommendations()
        assert pending
        item_id = pending[0]["item_id"]
        rec_id = pending[0]["recommendation_id"]
        ctrl.approve_recommendation(item_id, "operator-1")
        assert not ctrl.get_pending_recommendations()

        ctrl.register_baseline("hallucination_rate", 0.1)
        measurement = ctrl.measure_effectiveness(rec_id, "hallucination_rate", 0.05)
        assert measurement.improvement_pct == 50.0


class TestContinuousImprovementAPI:
    @pytest.fixture
    def client(self):
        import api_703
        api_703._ci_controller = ContinuousImprovementController()
        app = api_703.create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_feedback_and_analyze(self, client):
        for _ in range(4):
            resp = client.post("/api/v1/ci/feedback", json={
                "source": "complaint",
                "category": "hallucination",
                "severity": "high",
                "model_version": "m1",
                "prompt_version_id": "pv1",
                "message": "made up fact",
            })
            assert resp.status_code == 201
        analyze = client.post("/api/v1/ci/analyze", json={})
        assert analyze.status_code == 200
        data = analyze.get_json()["data"]
        assert data["systemic_clusters"] >= 1

    def test_recommendation_approval(self, client):
        for _ in range(4):
            client.post("/api/v1/ci/feedback", json={
                "source": "complaint",
                "category": "hallucination",
                "severity": "high",
                "model_version": "m1",
                "prompt_version_id": "pv1",
            })
        analyze = client.post("/api/v1/ci/analyze", json={})
        pending = client.get("/api/v1/ci/recommendations/pending").get_json()["data"]
        assert pending
        item_id = pending[0]["item_id"]
        approve = client.post("/api/v1/ci/recommendations/approve", json={
            "queue_item_id": item_id,
            "reviewer": "admin",
        })
        assert approve.status_code == 200

    def test_baseline_and_measure(self, client):
        resp = client.post("/api/v1/ci/baseline", json={
            "metric_name": "hallucination_rate",
            "value": 0.1,
        })
        assert resp.status_code == 201
        measure = client.post("/api/v1/ci/measure", json={
            "recommendation_id": "rec-1",
            "metric_name": "hallucination_rate",
            "value": 0.05,
        })
        assert measure.status_code == 201
        assert measure.get_json()["data"]["improvement_pct"] == 50.0

    def test_dashboard(self, client):
        resp = client.get("/api/v1/ci/dashboard")
        assert resp.status_code == 200
        assert "feedback_count" in resp.get_json()["data"]
