"""Tests para adaptive_incident_response.py — sistema inmunológico adaptativo."""
from __future__ import annotations

import pytest

from adaptive_incident_response import (
    AdaptiveIncidentEngine,
    ChallengeDataset,
    ChallengeScenario,
    ChaosRun,
    GoldenExample,
    IncidentPatternMiner,
    LLMReleaseGate,
    PlaybookGitOps,
    PlaybookVersion,
    ThreatIntelligenceFeed,
    ThreatLedChaosEngine,
    ThreatVector,
)


class TestThreatIntelligenceFeed:
    def test_default_atlas_loaded(self):
        feed = ThreatIntelligenceFeed()
        assert len(feed.list_vectors()) > 0
        assert any(v.mitre_atlas_technique for v in feed.list_vectors())

    def test_add_and_sync(self):
        feed = ThreatIntelligenceFeed()
        new = feed.sync([{
            "name": "New jailbreak",
            "category": "jailbreak",
            "severity": "high",
            "sample_prompts": ["prompt1"],
        }])
        assert len(new) == 1
        assert new[0].source == "external_sync"

    def test_coverage_by_category(self):
        feed = ThreatIntelligenceFeed()
        coverage = feed.coverage_by_category()
        assert any(coverage.values())


class TestIncidentPatternMiner:
    def test_mine_emerging_pattern(self):
        miner = IncidentPatternMiner(growth_threshold=0.1, min_frequency=2)
        incidents = [
            {"incident_id": "i1", "title": "jailbreak en español", "description": "nuevo patrón jailbreak"},
            {"incident_id": "i2", "title": "jailbreak detected", "description": "jailbreak pattern repeated"},
            {"incident_id": "i3", "title": "jailbreak again", "description": "same jailbreak attack"},
        ]
        patterns = miner.mine(incidents)
        assert patterns
        assert any("jailbreak" in p.signature for p in patterns)

    def test_confirm_pattern(self):
        miner = IncidentPatternMiner(growth_threshold=0.1, min_frequency=1)
        incidents = [{"incident_id": "i1", "title": "x", "description": "information leakage detected in system logs"}]
        patterns = miner.mine(incidents)
        assert patterns
        pat = patterns[0]
        assert miner.confirm_pattern(pat.pattern_id) is not None


class TestChallengeDataset:
    def test_add_scenario_and_validate(self):
        ds = ChallengeDataset()
        ds.add_scenario(ChallengeScenario(name="jailbreak", category="jailbreak", payload="p"))
        ds.add_scenario(ChallengeScenario(name="prompt injection", category="prompt_injection", payload="p"))
        result = ds.validate(lambda s: s.category == "jailbreak")
        assert result["pass_rate"] == 0.5

    def test_coverage(self):
        ds = ChallengeDataset()
        ds.add_scenario(ChallengeScenario(name="x", category="jailbreak", payload="p"))
        assert ds.coverage_percent({"jailbreak", "prompt_injection"}) == 0.5

    def test_golden_examples(self):
        ds = ChallengeDataset()
        ex = ds.add_golden_example(GoldenExample(prompt="p", corrected_label="blocked", category="jailbreak"))
        assert ex in ds.golden_examples()


class TestPlaybookGitOps:
    def test_commit_and_history(self):
        gitops = PlaybookGitOps()
        pb = gitops.commit("pb-jailbreak", "jailbreak", ["block"], {"threshold": 0.8}, "v1")
        assert pb.version == "v1"
        assert len(gitops.history("pb-jailbreak")) == 1

    def test_pr_flow(self):
        gitops = PlaybookGitOps()
        pr = gitops.propose_update("pb-jailbreak", "jailbreak", ["block", "log"], {"threshold": 0.7}, "add log")
        merged = gitops.merge_pr(pr["pr_id"])
        assert merged is not None
        assert merged.version == "v1"
        assert gitops.latest("pb-jailbreak").actions == ["block", "log"]


class TestThreatLedChaosEngine:
    def test_dry_run_chaos(self):
        ds = ChallengeDataset()
        ds.add_scenario(ChallengeScenario(name="jb", category="jailbreak", payload="p"))
        ds.add_scenario(ChallengeScenario(name="pi", category="prompt_injection", payload="p"))
        engine = ThreatLedChaosEngine(ds)
        run = engine.run(lambda s: s.category == "jailbreak", dry_run=True)
        assert isinstance(run, ChaosRun)
        assert run.pass_rate == 0.5
        assert any("Dry-run" in f for f in run.findings)


class TestLLMReleaseGate:
    def test_pass_release(self):
        ds = ChallengeDataset()
        ds.add_scenario(ChallengeScenario(name="jb", category="jailbreak", payload="p"))
        gate = LLMReleaseGate(ds, desired_categories={"jailbreak"}, min_pass_rate=0.95)
        report = gate.validate("llama-3.1", lambda s: True)
        assert report.passed

    def test_fail_release_due_low_pass_rate(self):
        ds = ChallengeDataset()
        ds.add_scenario(ChallengeScenario(name="jb", category="jailbreak", payload="p"))
        gate = LLMReleaseGate(ds, desired_categories={"jailbreak"}, min_pass_rate=0.95)
        report = gate.validate("llama-3.1", lambda s: False)
        assert not report.passed
        assert report.challenge_pass_rate == 0.0

    def test_fail_release_due_low_coverage(self):
        ds = ChallengeDataset()
        ds.add_scenario(ChallengeScenario(name="jb", category="jailbreak", payload="p"))
        gate = LLMReleaseGate(ds, desired_categories={"jailbreak", "prompt_injection"}, min_pass_rate=0.0)
        report = gate.validate("llama-3.1", lambda s: True)
        assert not report.passed


class TestAdaptiveIncidentEngine:
    def test_sync_adds_to_challenge_dataset(self):
        engine = AdaptiveIncidentEngine()
        res = engine.sync_threat_intelligence([{
            "name": "Fresh vector",
            "category": "jailbreak",
            "severity": "high",
            "sample_prompts": ["p"],
        }])
        assert res["new_vectors"] > 0
        assert engine.dataset.scenarios()

    def test_human_feedback_adds_golden(self):
        engine = AdaptiveIncidentEngine()
        ex = engine.record_human_feedback("prompt", "blocked", "jailbreak", human_reviewer="ana")
        assert ex in engine.dataset.golden_examples()

    def test_playbook_update_pr_merge(self):
        engine = AdaptiveIncidentEngine()
        pr = engine.propose_playbook_update("pb-1", "jailbreak", ["block"], {}, "fix")
        merged = engine.merge_playbook_pr(pr["pr_id"])
        assert merged is not None
        assert merged.version == "v1"

    def test_chaos_and_metrics(self):
        engine = AdaptiveIncidentEngine()
        engine.dataset.add_scenario(ChallengeScenario(name="jb", category="jailbreak", payload="p"))
        report = engine.run_chaos(lambda s: True, dry_run=True)
        assert report["pass_rate"] == 1.0
        metrics = engine.metrics()
        assert metrics["chaos_run_count"] == 1

    def test_validate_release(self):
        engine = AdaptiveIncidentEngine()
        engine.release_gate.desired_categories = {"jailbreak"}
        engine.dataset.add_scenario(ChallengeScenario(name="jb", category="jailbreak", payload="p"))
        report = engine.validate_release("llama-3.1", lambda s: True)
        assert report["passed"]
        assert report["challenge_pass_rate"] == 1.0

    def test_record_false_negative(self):
        engine = AdaptiveIncidentEngine()
        engine.record_false_negative("inc-1", "jailbreak", "rule-1")
        metrics = engine.metrics()
        assert metrics["false_negatives_30d"] == 1


class TestOrchestratorIntegration:
    def test_orchestrator_adaptive_metrics(self):
        from continuous_training_orchestrator import ContinuousTrainingOrchestrator
        orch = ContinuousTrainingOrchestrator()
        orch.add_challenge_scenario({"name": "jb", "category": "jailbreak", "payload": "p"})
        metrics = orch.adaptive_metrics()
        assert "threat_vectors_count" in metrics
        assert "challenge_coverage_percent" in metrics

    def test_orchestrator_release_gate(self):
        from continuous_training_orchestrator import ContinuousTrainingOrchestrator
        orch = ContinuousTrainingOrchestrator()
        orch.add_challenge_scenario({"name": "jb", "category": "jailbreak", "payload": "p"})
        orch.adaptive_engine.release_gate.desired_categories = {"jailbreak"}
        report = orch.validate_release_with_challenge(
            model_version="llama-3.1",
            detector=lambda s: True,
        )
        assert report["passed"]
