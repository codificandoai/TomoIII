"""Tests para PreProductionQualityGate en UC-703."""
from __future__ import annotations

import pytest

from fine_tuning.quality_gate.cross_team_approval import CrossTeamApprovalGate
from fine_tuning.quality_gate.dataset_loader import DatasetLoader
from fine_tuning.quality_gate.evaluators import (
    BaselineComparator,
    QualitativeEvaluator,
    QuantitativeEvaluator,
)
from fine_tuning.quality_gate.models_quality import QualitativeReview
from fine_tuning.quality_gate.observability import LokiLogger, PrometheusExporter, WikiPublisher
from fine_tuning.quality_gate.quality_gate_controller import QualityGateController


class TestDatasetLoader:
    def test_load_by_category(self):
        loader = DatasetLoader()
        records = [
            {"category": "use_case", "risk_level": "low", "input_text": "q1", "expected_output": "a1"},
            {"category": "edge_case", "risk_level": "high", "input_text": "q2", "expected_output": "a2"},
            {"category": "adversarial", "risk_level": "critical", "input_text": "q3", "expected_output": "a3"},
            {"category": "real_user", "risk_level": "medium", "input_text": "q4", "expected_output": "a4"},
        ]
        ds = loader.load_from_records("eval-1", records)
        assert len(ds.samples) == 4
        assert set(ds.by_category().keys()) == {"use_case", "edge_case", "adversarial", "real_user"}

    def test_invalid_category_raises(self):
        loader = DatasetLoader()
        with pytest.raises(ValueError):
            loader.load_from_records("bad", [{"category": "unknown"}])


class TestQuantitativeEvaluator:
    def test_passes_with_lenient_thresholds(self):
        ev = QuantitativeEvaluator(thresholds={
            "accuracy": 0.1, "relevance": 0.1, "safety": 0.1,
            "toxicity_rate": 1.0, "jailbreak_rejection_rate": 0.0,
            "bias_score": 1.0, "latency_ms_p95": 1e6, "cost_per_1k_tokens": 1.0,
        })
        ds = DatasetLoader().load_from_records("e", [{"input_text": "x", "expected_output": "y"}])
        metrics = ev.evaluate(ds)
        assert metrics.passed

    def test_fails_with_strict_thresholds(self):
        ev = QuantitativeEvaluator(thresholds={
            "accuracy": 1.0, "relevance": 1.0, "safety": 1.0,
            "toxicity_rate": 0.0, "jailbreak_rejection_rate": 1.0,
            "bias_score": 0.0, "latency_ms_p95": 0.0, "cost_per_1k_tokens": 0.0,
        })
        ds = DatasetLoader().load_from_records("e", [{"input_text": "x", "expected_output": "y"}])
        metrics = ev.evaluate(ds)
        assert not metrics.passed
        assert metrics.failures


class TestQualitativeEvaluator:
    def test_summary_pass(self):
        ev = QualitativeEvaluator(min_correctness=2, min_helpfulness=2, min_safety=3)
        reviews = [
            QualitativeReview(reviewer_role="domain_expert", sample_id="s1", correctness=4, helpfulness=4, safety=5),
            QualitativeReview(reviewer_role="target_user", sample_id="s2", correctness=4, helpfulness=4, safety=5),
        ]
        summary = ev.summarize(reviews)
        assert summary.passed

    def test_summary_fail_safety(self):
        ev = QualitativeEvaluator(min_safety=5)
        reviews = [QualitativeReview(reviewer_role="target_user", sample_id="s1", correctness=5, helpfulness=5, safety=3)]
        summary = ev.summarize(reviews)
        assert not summary.passed


class TestBaselineComparator:
    def test_no_regression(self):
        cmp = BaselineComparator(max_regression_pct=10)
        current = {"accuracy": 0.85}
        baseline = {"accuracy": 0.82}
        previous = {"accuracy": 0.80}
        result = cmp.compare(current, baseline, previous, higher_is_better=["accuracy"])
        assert result.passed
        assert result.deltas_vs_baseline["accuracy"] == 0.03

    def test_regression_detected(self):
        cmp = BaselineComparator(max_regression_pct=5)
        current = {"accuracy": 0.70}
        baseline = {"accuracy": 0.80}
        previous = {"accuracy": 0.78}
        result = cmp.compare(current, baseline, previous, higher_is_better=["accuracy"])
        assert not result.passed
        assert result.regressions


class TestObservability:
    def test_prometheus_records(self):
        exporter = PrometheusExporter()
        exporter.record("run-1", {"accuracy": 0.9}, "passed")
        exporter.record_baseline_delta("run-1", {"accuracy": 0.05})
        text = exporter.render()
        assert "llm_eval_accuracy" in text
        assert "llm_eval_baseline_delta" in text

    def test_loki_logger(self):
        logger = LokiLogger()
        logger.log("test", "run-1", "step", "ok", {"x": 1})
        assert len(logger.get_entries()) == 1

    def test_wiki_publisher(self):
        pub = WikiPublisher()
        md = "# report"
        result = pub.publish("r1", md)
        assert result["uri"]
        assert result["digest"]


class TestCrossTeamApproval:
    def test_full_approval(self):
        gate = CrossTeamApprovalGate()
        approval = gate.request_approval("run-1", "report-1")
        assert approval.status == "pending"
        gate.submit_signature(approval.approval_id, "engineering", "eng@tomo.ai")
        gate.submit_signature(approval.approval_id, "compliance", "compliance@tomo.ai")
        gate.submit_signature(approval.approval_id, "business", "biz@tomo.ai")
        assert approval.is_approved()
        assert approval.status == "approved"

    def test_reject_blocks(self):
        gate = CrossTeamApprovalGate()
        approval = gate.request_approval("run-1", "report-1")
        gate.reject(approval.approval_id, "compliance", "ethical risk")
        assert approval.status == "rejected"


class TestQualityGateController:
    def test_full_gate_pass_no_approval(self):
        qg = QualityGateController(
            quantitative=QuantitativeEvaluator(thresholds={
                "accuracy": 0.0, "relevance": 0.0, "safety": 0.0,
                "toxicity_rate": 1.0, "jailbreak_rejection_rate": 0.0,
                "bias_score": 1.0, "latency_ms_p95": 1e6, "cost_per_1k_tokens": 1.0,
            })
        )
        records = [{"category": "use_case", "risk_level": "low", "input_text": "q", "expected_output": "a"}]
        ds = qg.load_dataset("eval", records)
        reviews = [QualitativeReview(reviewer_role="domain_expert", sample_id="s1", correctness=5, helpfulness=5, safety=5)]
        report = qg.run_full_gate(
            run_id="run-pass",
            model_version="llama-7b",
            dataset=ds,
            baseline_metrics={"accuracy": 0.0, "relevance": 0.0},
            previous_metrics={"accuracy": 0.0, "relevance": 0.0},
            reviews=reviews,
            request_approval=False,
        )
        assert report.status == "approved"
        assert report.evidence_uris.get("wiki_report")

    def test_full_gate_blocked_by_quantitative(self):
        qg = QualityGateController(
            quantitative=QuantitativeEvaluator(thresholds={
                "accuracy": 1.0, "relevance": 1.0, "safety": 1.0,
                "toxicity_rate": 0.0, "jailbreak_rejection_rate": 1.0,
                "bias_score": 0.0, "latency_ms_p95": 0.0, "cost_per_1k_tokens": 0.0,
            })
        )
        records = [{"category": "use_case", "risk_level": "low", "input_text": "q", "expected_output": "a"}]
        ds = qg.load_dataset("eval", records)
        report = qg.run_full_gate(
            run_id="run-block",
            model_version="llama-7b",
            dataset=ds,
            baseline_metrics={"accuracy": 0.9},
            previous_metrics={"accuracy": 0.9},
            request_approval=False,
        )
        assert report.status == "blocked"
        assert report.findings

    def test_approval_flow(self):
        qg = QualityGateController(
            quantitative=QuantitativeEvaluator(thresholds={
                "accuracy": 0.0, "relevance": 0.0, "safety": 0.0,
                "toxicity_rate": 1.0, "jailbreak_rejection_rate": 0.0,
                "bias_score": 1.0, "latency_ms_p95": 1e6, "cost_per_1k_tokens": 1.0,
            })
        )
        records = [{"category": "use_case", "risk_level": "low", "input_text": "q", "expected_output": "a"}]
        ds = qg.load_dataset("eval", records)
        reviews = [QualitativeReview(reviewer_role="domain_expert", sample_id="s1", correctness=5, helpfulness=5, safety=5)]
        report = qg.run_full_gate(
            run_id="run-approval",
            model_version="llama-7b",
            dataset=ds,
            baseline_metrics={"accuracy": 0.0, "relevance": 0.0},
            previous_metrics={"accuracy": 0.0, "relevance": 0.0},
            reviews=reviews,
            request_approval=True,
        )
        assert report.status == "awaiting_approval"
        qg.submit_approval_signature(report.cross_team_approval.approval_id, "engineering", "eng")
        qg.submit_approval_signature(report.cross_team_approval.approval_id, "compliance", "compliance")
        qg.submit_approval_signature(report.cross_team_approval.approval_id, "business", "biz")
        updated = qg.get_report(report.report_id)
        assert updated.status == "approved"


class TestQualityGateAPIIntegration:
    @pytest.fixture
    def client(self):
        from api_703 import create_app
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_list_reports_empty(self, client):
        resp = client.get("/api/v1/ft/quality-gate/reports")
        assert resp.status_code == 200
        assert resp.get_json()["data"] == []

    def test_run_quality_gate_missing_fields(self, client):
        resp = client.post("/api/v1/ft/quality-gate/run", json={"pipeline_id": "x"})
        assert resp.status_code == 400

    def test_approve_missing_fields(self, client):
        resp = client.post("/api/v1/ft/quality-gate/approve", json={"pipeline_id": "x"})
        assert resp.status_code == 400
