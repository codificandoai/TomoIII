"""Tests para FineTuningController y agents."""
from __future__ import annotations

import pytest

from fine_tuning.controller import FineTuningController
from fine_tuning.data_agents import DataCurationAgent, DatasetVersionRegistry, LeakageAuditAgent
from fine_tuning.evaluation_agents import AlignmentAgent, EvaluationAgent, PromotionGate
from fine_tuning.models_ft import FeedbackItem
from fine_tuning.serving_agents import CanaryMonitor, DeploymentAgent, DriftHallucinationAgent, FeedbackLoopAgent
from fine_tuning.models_ft import TrainingRunConfig
from fine_tuning.training_agents import HyperparameterSearchAgent, ResourcePlannerAgent, TrainingSREAgent


class TestDataAgents:
    def test_curation_dedup_and_flag_short(self):
        agent = DataCurationAgent(template="t")
        raw = [
            {"instruction": "hello world"},
            {"instruction": "hello world"},
            {"instruction": "hi"},
        ]
        result = agent.curate(raw, dataset_id="ds-1")
        assert result.cleaned_samples == 2
        assert result.duplicates_removed == 1
        assert result.hitl_flagged_samples

    def test_leakage_audit_pass(self):
        agent = LeakageAuditAgent(ngram_threshold=0.9, embedding_threshold=0.99)
        train = [{"text": "a b c d e f"}]
        eval_ = [{"text": "x y z"}]
        report = agent.audit(train, eval_, dataset_id="ds-1")
        assert report.passed

    def test_leakage_audit_fail(self):
        agent = LeakageAuditAgent(ngram_threshold=0.05, embedding_threshold=0.8)
        train = [{"text": "a b c d e f"}]
        eval_ = [{"text": "a b c d e f"}]
        report = agent.audit(train, eval_, dataset_id="ds-1")
        assert not report.passed

    def test_dataset_registry_hash_and_verify(self):
        reg = DatasetVersionRegistry()
        dv = reg.register("ds-1", "template", 42, {"train": "uri"}, 100)
        assert dv.audit_hash
        assert reg.verify_template_matches("ds-1", "template")
        assert not reg.verify_template_matches("ds-1", "other")


class TestTrainingAgents:
    def test_resource_planner_qlora(self):
        planner = ResourcePlannerAgent()
        plan = planner.plan(model_size_b=7, dataset_samples=10_000, budget_usd=100, deadline_hours=2)
        assert plan.strategy == "qlora"

    def test_resource_planner_full(self):
        planner = ResourcePlannerAgent()
        plan = planner.plan(model_size_b=100, dataset_samples=1_000_000, budget_usd=10_000, deadline_hours=24)
        assert plan.strategy == "full"

    def test_training_sre_diagnose_oom(self):
        sre = TrainingSREAgent()
        cfg = TrainingRunConfig(dataset_id="ds-1", base_model="m")
        sre.register_job(cfg)
        sre.emit_metric(cfg.run_id, {"oom": True})
        diag = sre.diagnose(cfg.run_id)
        assert diag["action"] == "reduce_batch"

    def test_hp_search_prunes_and_best(self):
        hp = HyperparameterSearchAgent(max_trials=4)
        trials = hp.suggest_trials()
        for t in trials:
            hp.report_trial_result(t.trial_id, 1.0 if t.trial_id.endswith("0") else 0.5, False)
        best = hp.best_trial()
        assert best is not None
        assert best.score == 0.5


class TestEvaluationAgents:
    def test_evaluation_pass(self):
        eval_agent = EvaluationAgent()
        domain = [{"correct": 1} for _ in range(10)]
        general = [{"correct": 1} for _ in range(10)]
        report = eval_agent.evaluate("run-1", domain, general, baseline_general_score=1.0)
        assert report.domain_score == 1.0

    def test_promotion_gate_blocks_low_domain(self):
        gate = PromotionGate(min_domain_score=0.9)
        report = EvaluationAgent().evaluate("run-1", [{"correct": 0}], [{"correct": 1}], 1.0)
        decision = gate.decide(report)
        assert not decision["passed"]

    def test_alignment_recommends_dpo(self):
        agent = AlignmentAgent()
        rec = agent.recommend("finance", "low", 5000, True)
        assert rec["recommended_method"] == "DPO"
        assert not rec["requires_hitl"]


class TestServingAgents:
    def test_bundle_hash(self):
        dep = DeploymentAgent()
        bundle = dep.build_bundle("base", "adapter", "prompt", {"temp": 0.7}, "ds-1", "run-1")
        assert bundle.audit_hash

    def test_canary_pass(self):
        monitor = CanaryMonitor()
        assessment = monitor.assess(
            {"error_rate": 0.01, "latency_p95_ms": 100, "success_rate": 0.99},
            {"success_rate": 0.98},
        )
        assert assessment["passed"]

    def test_canary_fail_latency(self):
        monitor = CanaryMonitor()
        assessment = monitor.assess(
            {"error_rate": 0.01, "latency_p95_ms": 1000, "success_rate": 0.99},
            {"success_rate": 0.98},
        )
        assert not assessment["passed"]

    def test_drift_detected(self):
        agent = DriftHallucinationAgent(
            data_drift_threshold=0.01,
            concept_drift_threshold=0.01,
            hallucination_threshold=0.01,
        )
        report = agent.analyze("dep-1", ["input"], ["output with unknowninformation"], ["context"])
        assert report.threshold_violated

    def test_feedback_loop_triggers_retrain(self):
        loop = FeedbackLoopAgent(min_feedback_to_trigger=2)
        loop.ingest(FeedbackItem(deployment_id="d1", input_text="i", output_text="o", label="bad"))
        loop.ingest(FeedbackItem(deployment_id="d1", input_text="i2", output_text="o2", label="bad"))
        cycle = loop.should_trigger_retrain("d1")
        assert cycle is not None


class TestFineTuningController:
    def test_full_pipeline_pass(self):
        ctrl = FineTuningController()
        raw = [
            {"instruction": "say hello", "output": "hi"},
            {"instruction": "say goodbye", "output": "bye"},
        ]
        state = ctrl.curate_and_register(
            dataset_id="ds-pass",
            raw_samples=raw,
            prompt_template="chat-v1",
            train_eval_samples={
                "train": raw,
                "eval": [{"instruction": "completely different long phrase about quantum mechanics", "output": "answer unrelated to greetings"}],
            },
        )
        assert state.status == "curated"
        ctrl.plan_resources(state.pipeline_id, model_size_b=7, budget_usd=100, deadline_hours=2)
        ctrl.run_hp_search(state.pipeline_id)
        ctrl.create_training_config(state.pipeline_id, base_model="llama-7b")
        ctrl.simulate_training_step(state.pipeline_id, {"loss": 1.0})
        decision = ctrl.evaluate(
            state.pipeline_id,
            domain_results=[{"correct": 1} for _ in range(10)],
            general_results=[{"correct": 1} for _ in range(10)],
            baseline_general_score=1.0,
        )
        assert decision["passed"]
        rec = ctrl.recommend_alignment(state.pipeline_id, "finance", "low", True)
        assert rec["recommended_method"]
        ctrl.build_and_deploy_canary(state.pipeline_id, adapter_uri="s3://adapter", generation_params={"temp": 0.7})
        assessment = ctrl.assess_canary(
            state.pipeline_id,
            canary_metrics={"error_rate": 0.01, "latency_p95_ms": 100, "success_rate": 0.99},
            baseline_metrics={"success_rate": 0.98},
        )
        assert assessment["passed"]
        assert state.status == "stable"

    def test_pipeline_blocked_by_leakage(self):
        ctrl = FineTuningController()
        raw = [{"instruction": "duplicate"}]
        state = ctrl.curate_and_register(
            dataset_id="ds-leak",
            raw_samples=raw,
            prompt_template="chat-v1",
            train_eval_samples={"train": raw, "eval": raw},
        )
        assert state.status == "blocked_leakage"

    def test_feedback_triggers_closed_loop(self):
        ctrl = FineTuningController()
        raw = [{"instruction": "x", "output": "y"}]
        state = ctrl.curate_and_register("ds-fb", raw, "t")
        ctrl.plan_resources(state.pipeline_id, model_size_b=7, budget_usd=100, deadline_hours=2)
        ctrl.create_training_config(state.pipeline_id, base_model="llama-7b")
        ctrl.build_and_deploy_canary(state.pipeline_id, adapter_uri="s3://adapter", generation_params={})
        for _ in range(10):
            ctrl.ingest_feedback(state.pipeline_id, FeedbackItem(
                deployment_id=state.deployment.deployment_id,
                input_text="i",
                output_text="o",
                label="bad",
            ))
        assert state.status == "retrain_scheduled"
        assert state.closed_loop is not None


class TestFineTuningAPIIntegration:
    def test_api_curate_and_pipeline(self, client):
        resp = client.post("/api/v1/ft/curate-and-register", json={
            "dataset_id": "ds-api",
            "raw_samples": [{"instruction": "hello", "output": "hi"}],
            "prompt_template": "t",
        })
        assert resp.status_code == 201
        pipeline_id = resp.get_json()["data"]["pipeline_id"]

        resp = client.post("/api/v1/ft/plan-resources", json={
            "pipeline_id": pipeline_id,
            "model_size_b": 7,
            "budget_usd": 100,
            "deadline_hours": 2,
        })
        assert resp.status_code == 200

        resp = client.post("/api/v1/ft/create-training-config", json={
            "pipeline_id": pipeline_id,
            "base_model": "llama-7b",
        })
        assert resp.status_code == 200

        resp = client.get(f"/api/v1/ft/pipelines/{pipeline_id}")
        assert resp.status_code == 200


# Provide fixture for TestFineTuningAPIIntegration in conftest or here
from api_703 import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
