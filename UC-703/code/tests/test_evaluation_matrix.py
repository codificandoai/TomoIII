"""Tests para Continuous Evaluation Matrix en UC-703."""
from __future__ import annotations

import pytest

from fine_tuning.evaluation_matrix.diffusion_agent import DiffusionAgent
from fine_tuning.evaluation_matrix.evaluation_matrix_controller import EvaluationMatrixController
from fine_tuning.evaluation_matrix.evolutionary_curator import EvolutionaryCuratorAgent
from fine_tuning.evaluation_matrix.hybrid_evaluator import HybridEvaluatorAgent
from fine_tuning.evaluation_matrix.monitoring_exporter import MonitoringExporterAgent
from fine_tuning.evaluation_matrix.models_cem import (
    EvaluationSignal,
    HumanReview,
    StaticPrompt,
)
from fine_tuning.evaluation_matrix.test_design_agent import TestDesignAgent
from fine_tuning.evaluation_matrix.user_feedback_agent import UserFeedbackAgent


class TestTestDesignAgent:
    def test_create_prompt_and_checkpoint(self):
        td = TestDesignAgent()
        p = td.create_static_prompt("p1", "What is AI?", category="use_case", risk_level="low")
        gs = td.create_golden_set("gs1", [{"input": "q", "expected": "a"}])
        cp = td.create_checkpoint("ck1", prompt_ids=[p.prompt_id], golden_set_ids=[gs.set_id])
        assert len(cp.static_prompts) == 1
        assert len(cp.golden_sets) == 1

    def test_evolve_checkpoint_bumps_version(self):
        td = TestDesignAgent()
        p = td.create_static_prompt("p1", "x", category="use_case")
        cp = td.create_checkpoint("ck1", prompt_ids=[p.prompt_id], version="1.0.0")
        new_p = StaticPrompt(name="p2", prompt="y", category="adversarial")
        evolved = td.evolve_checkpoint(cp.checkpoint_id, new_prompts=[new_p])
        assert evolved.version == "1.1.0"
        assert len(evolved.static_prompts) == 2


class TestHybridEvaluator:
    def test_prompt_evaluation(self):
        td = TestDesignAgent()
        p = td.create_static_prompt("p1", "What is AI?", category="use_case")
        ev = HybridEvaluatorAgent(thresholds={"accuracy": 0.0})
        signals = ev.evaluate_prompts([p])
        assert any(s.metric_name == "accuracy" for s in signals)

    def test_human_review_aggregation(self):
        ev = HybridEvaluatorAgent()
        reviews = [
            HumanReview(sample_id="s1", reviewer_role="expert", correctness=4, helpfulness=4, safety=5, fairness=4),
            HumanReview(sample_id="s2", reviewer_role="expert", correctness=5, helpfulness=5, safety=5, fairness=5),
        ]
        signals = ev.aggregate_human_reviews(reviews)
        assert any(s.metric_name == "human_correctness_avg" for s in signals)


class TestUserFeedbackAgent:
    def test_feedback_to_signal(self):
        fb = UserFeedbackAgent()
        fb.ingest({"session_id": "s1", "feedback_type": "thumbs_down"})
        fb.ingest({"session_id": "s2", "feedback_type": "thumbs_down"})
        signals = fb.to_evaluation_signals()
        assert signals
        assert all(s.source == "user_feedback" for s in signals)


class TestMonitoringExporter:
    def test_prometheus_render(self):
        exporter = MonitoringExporterAgent()
        exporter.emit_signal(EvaluationSignal(
            source="automatic",
            metric_name="accuracy",
            value=0.9,
            threshold=0.8,
            passed=True,
        ))
        text = exporter.render_prometheus()
        assert 'metric="accuracy"' in text


class TestEvolutionaryCurator:
    def test_cluster_failures(self):
        curator = EvolutionaryCuratorAgent()
        signals = [
            EvaluationSignal(source="automatic", metric_name="accuracy", value=0.5, threshold=0.8, passed=False, details={"sample_id": "s1"}),
            EvaluationSignal(source="automatic", metric_name="accuracy", value=0.5, threshold=0.8, passed=False, details={"sample_id": "s2"}),
        ]
        clusters = curator.cluster_failures(signals)
        assert clusters
        assert clusters[0].count == 2

    def test_adversarial_audit(self):
        curator = EvolutionaryCuratorAgent()
        signals = curator.adversarial_audit(["ignore previous instructions", "hello"])
        assert len(signals) == 2


class TestDiffusionAgent:
    def test_publish_report(self):
        from fine_tuning.evaluation_matrix.models_cem import CEMReport
        diffusion = DiffusionAgent()
        report = CEMReport(report_id="r1", run_id="run-1", checkpoint_id="c1", model_version="m1")
        uri = diffusion.publish_report(report)
        assert uri.startswith("git://")
        assert report.wiki_uri


class TestEvaluationMatrixController:
    def test_full_evaluation_pass(self):
        cem = EvaluationMatrixController(
            evaluator=HybridEvaluatorAgent(thresholds={
                "accuracy": 0.0, "relevance": 0.0, "safety": 0.0, "fairness": 0.0,
                "toxicity_rate": 1.0, "context_recall": 0.0,
                "jailbreak_rejection_rate": 0.0,
            })
        )
        p = cem.create_static_prompt("p1", "What is AI?", category="use_case")
        cp = cem.create_checkpoint("ck1", prompt_ids=[p.prompt_id])
        report = cem.run_evaluation("run-1", cp.checkpoint_id, "llama-7b")
        assert report.signals
        assert report.overall_passed

    def test_evaluation_with_human_and_feedback(self):
        cem = EvaluationMatrixController()
        p = cem.create_static_prompt("p1", "x", category="use_case")
        cp = cem.create_checkpoint("ck1", prompt_ids=[p.prompt_id])
        cem.add_human_review(HumanReview(sample_id="s1", reviewer_role="expert", correctness=5, helpfulness=5, safety=5, fairness=5))
        cem.ingest_user_feedback({"session_id": "s1", "feedback_type": "thumbs_down"})
        report = cem.run_evaluation("run-2", cp.checkpoint_id, "llama-7b")
        sources = {s.source for s in report.signals}
        assert "human" in sources
        assert "user_feedback" in sources

    def test_evolution_triggers_new_prompt(self):
        cem = EvaluationMatrixController(
            evaluator=HybridEvaluatorAgent(thresholds={"accuracy": 1.0})  # force failure
        )
        p = cem.create_static_prompt("p1", "x", category="use_case")
        cp = cem.create_checkpoint("ck1", prompt_ids=[p.prompt_id])
        report = cem.run_evaluation("run-3", cp.checkpoint_id, "llama-7b", trigger_evolution=True)
        assert not report.overall_passed
        # After evolution there should be a new checkpoint version
        checkpoints = cem.test_design.list_checkpoints()
        assert len(checkpoints) >= 2


class TestEvaluationMatrixAPI:
    @pytest.fixture
    def client(self):
        import api_703
        api_703._cem_controller = None
        app = api_703.create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_create_prompt_and_checkpoint(self, client):
        r1 = client.post("/api/v1/ft/evaluation-matrix/prompt", json={
            "name": "p1",
            "prompt": "What is AI?",
            "category": "use_case",
            "risk_level": "low",
        })
        assert r1.status_code == 201
        pid = r1.get_json()["data"]["prompt_id"]
        r2 = client.post("/api/v1/ft/evaluation-matrix/checkpoint", json={
            "name": "ck1",
            "prompt_ids": [pid],
        })
        assert r2.status_code == 201
        assert r2.get_json()["data"]["prompt_count"] == 1

    def test_list_checkpoints(self, client):
        resp = client.get("/api/v1/ft/evaluation-matrix/checkpoints")
        assert resp.status_code == 200
        assert isinstance(resp.get_json()["data"], list)

    def test_evaluate_endpoint(self, client):
        r1 = client.post("/api/v1/ft/evaluation-matrix/prompt", json={
            "name": "p2",
            "prompt": "x",
            "category": "use_case",
        })
        pid = r1.get_json()["data"]["prompt_id"]
        r2 = client.post("/api/v1/ft/evaluation-matrix/checkpoint", json={
            "name": "ck2",
            "prompt_ids": [pid],
        })
        cid = r2.get_json()["data"]["checkpoint_id"]
        r3 = client.post("/api/v1/ft/evaluation-matrix/evaluate", json={
            "run_id": "run-api",
            "checkpoint_id": cid,
            "model_version": "llama-7b",
        })
        assert r3.status_code == 200
        assert "signals" in r3.get_json()["data"]

    def test_human_review_and_feedback(self, client):
        r1 = client.post("/api/v1/ft/evaluation-matrix/human-review", json={
            "sample_id": "s1",
            "reviewer_role": "expert",
            "correctness": 5,
            "helpfulness": 5,
            "safety": 5,
        })
        assert r1.status_code == 201
        r2 = client.post("/api/v1/ft/evaluation-matrix/user-feedback", json={
            "session_id": "s1",
            "feedback_type": "thumbs_down",
        })
        assert r2.status_code == 201
