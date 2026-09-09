"""Tests unitarios e integración para UC-075 Continuous Training Orchestrator."""
from __future__ import annotations

import time

import pytest

from models_075 import (
    GateName,
    GateVerdict,
    OrchestratorPolicy,
    PipelineStatus,
    RetrainStrategy,
    SecurityFairnessReport,
    CanaryReport,
)
from trigger_engine import TriggerEngine
from gate_pipeline import GatePipeline
from registry_075 import ChampionRegistry, VersionFreezeRegistry
from observability_075 import Observability075
from continuous_training_orchestrator import (
    AuditLog,
    ContinuousTrainingOrchestrator,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def winning_matchup_trainer(records):
    return {
        "version_id": "cand-good",
        "metrics": {"accuracy": 0.9, "replay_accuracy": 0.9},
        "cost_usd": 1.0,
    }


def losing_matchup_trainer(records):
    return {
        "version_id": "cand-bad",
        "metrics": {"accuracy": 0.7, "replay_accuracy": 0.7},
        "cost_usd": 1.0,
    }


def make_orchestrator(trainer=None, hitl_approver=None, canary_monitor=None,
                      security_fairness=None, policy=None, sink_events=None, **_):
    events = [] if sink_events is None else sink_events
    return ContinuousTrainingOrchestrator(
        policy=policy or OrchestratorPolicy(),
        trainer=trainer or winning_matchup_trainer,
        evaluator=lambda records, champ: {
            "accuracy": champ.get("accuracy", 0.8) + 0.05,
            "replay_accuracy": champ.get("accuracy", 0.8) + 0.05,
            "out_of_sample": 1,
        },
        hitl_approver=hitl_approver,
        canary_monitor=canary_monitor,
        security_fairness=security_fairness,
        event_sink=events.append,
        mlflow_enabled=False,
    ), events


# ---------------------------------------------------------------------------
# TriggerEngine — unitarios
# ---------------------------------------------------------------------------

class TestTriggerEngine:
    def test_event_trigger_on_drift(self):
        eng = TriggerEngine(OrchestratorPolicy(drift_score_threshold=0.2))
        t = eng.evaluate_event({"drift_score": 0.5})
        assert t is not None
        assert t.strategy == RetrainStrategy.EVENT_DRIVEN
        assert "drift" in t.reason

    def test_event_trigger_multiple_breaches(self):
        eng = TriggerEngine(OrchestratorPolicy(error_rate_threshold=0.05))
        t = eng.evaluate_event({
            "drift_score": 0.9,
            "error_rate": 0.10,
            "user_satisfaction": 0.5,
        })
        assert t is not None
        assert "error_rate" in t.reason and "user_satisfaction" in t.reason

    def test_event_no_trigger_when_healthy(self):
        eng = TriggerEngine()
        assert eng.evaluate_event({"drift_score": 0.01}) is None

    def test_scheduled_due_interval(self):
        eng = TriggerEngine()
        t = eng.scheduled_due("agent-1", interval_hours=24)
        assert t is not None
        eng.mark_scheduled_run("agent-1")
        assert eng.scheduled_due("agent-1", interval_hours=24) is None

    def test_on_demand_trigger(self):
        eng = TriggerEngine()
        t = eng.on_demand("policy_change", "Nueva normativa ISO 42001")
        assert t.strategy == RetrainStrategy.ON_DEMAND
        assert t.business_trigger == "policy_change"

    def test_incremental_requires_data(self):
        eng = TriggerEngine()
        assert eng.incremental([], []) is None
        t = eng.incremental([{"f": 1}], [{"f": 0}])
        assert t is not None and t.strategy == RetrainStrategy.INCREMENTAL

    def test_budget_blocks_exceeding_trigger(self):
        policy = OrchestratorPolicy(max_retrain_cost_usd=10.0)
        eng = TriggerEngine(policy)
        t = eng.on_demand("product_change", "x", estimated_cost_usd=100.0)
        decision = eng.evaluate_policy(t)
        assert not decision.proceed
        assert any("budget" in v for v in decision.policy_violations)

    def test_daily_cap_blocks(self):
        policy = OrchestratorPolicy(max_retrains_per_day=1)
        eng = TriggerEngine(policy)
        t = eng.on_demand("product_change", "x")
        assert eng.evaluate_policy(t).proceed
        eng.register_spend(t, 1.0)
        decision = eng.evaluate_policy(eng.on_demand("product_change", "y"))
        assert not decision.proceed

    def test_incremental_requires_replay(self):
        eng = TriggerEngine()
        t = eng.incremental([{"f": 1}], [])
        decision = eng.evaluate_policy(t)
        assert not decision.proceed
        assert "incremental_without_replay" in decision.policy_violations


# ---------------------------------------------------------------------------
# Gates — unitarios
# ---------------------------------------------------------------------------

class TestGates:
    def test_hitl_requires_review_for_high_impact(self):
        orch = ContinuousTrainingOrchestrator(
            policy=OrchestratorPolicy(auto_approve_max_risk=0.0),
            trainer=winning_matchup_trainer,
            evaluator=lambda r, c: {
                "accuracy": c.get("accuracy", 0.8) + 0.05,
                "replay_accuracy": 0.9,
                "out_of_sample": 1,
            },
            hitl_approver=lambda run: None,
            mlflow_enabled=False,
        )
        result = orch.on_demand("agent-hi", "policy_change", "medical update", domain="medical")
        assert result.status == PipelineStatus.PENDING_HITL
        assert result.gates[-1].gate == GateName.HITL
        assert result.gates[-1].verdict == GateVerdict.REQUIRES_HITL

    def test_security_fairness_fail_blocks(self):
        def bad_sf(matchup):
            return SecurityFairnessReport(bias_detected=True, violations=["gender bias"])
        orch, _ = make_orchestrator(security_fairness=bad_sf)
        run = orch.on_demand("agent-1", "product_change", "x")
        assert run.status == PipelineStatus.REJECTED
        assert run.gates[-1].gate == GateName.SECURITY_FAIRNESS

    def test_canary_fail_triggers_rollback(self):
        def unhealthy(candidate, ratio):
            return CanaryReport(candidate_version=candidate, traffic_ratio=ratio,
                                duration_sec=10.0, error_rate=0.5, healthy=False)
        orch, _ = make_orchestrator(canary_monitor=unhealthy)
        run1 = orch.on_demand("agent-c", "x", "first")
        # run1 promoted (candidate healthy via default monitor in first orch?) — re-create
        orch2, _ = make_orchestrator(canary_monitor=unhealthy)
        run2 = orch2.on_demand("agent-c", "x", "second")
        assert run2.status == PipelineStatus.ROLLED_BACK

    def test_champion_loser_rejected(self):
        orch, _ = make_orchestrator(
            trainer=losing_matchup_trainer,
        )
        orch.evaluator = lambda r, c: {"accuracy": c.get("accuracy", 0.8) - 0.1,
                                       "replay_accuracy": 0.8, "out_of_sample": 1}
        run = orch.on_demand("agent-l", "x", "y")
        assert run.status == PipelineStatus.REJECTED
        assert run.gates[-1].gate == GateName.CHAMPION_CHALLENGER


# ---------------------------------------------------------------------------
# Registry / freeze — unitarios
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_freeze_version_and_verify(self):
        reg = VersionFreezeRegistry()
        snap = reg.freeze([{"f": 1}])
        assert snap.dataset_version
        assert reg.verify(snap.dataset_version)
        # tamper
        snap.records[0]["f"] = 999
        assert not reg.verify(snap.dataset_version)

    def test_champion_rollback(self):
        reg = ChampionRegistry()
        champ = reg.bootstrap("a")
        reg.register_canary("a", "v2", {"accuracy": 0.9})
        reg.promote("a", "v2")
        assert reg.current_champion("a").version_id == "v2"
        restored = reg.rollback("a")
        assert restored.version_id == champ.version_id


# ---------------------------------------------------------------------------
# Observability — unitarios
# ---------------------------------------------------------------------------

class TestObservability:
    def test_prometheus_text_contains_uc075(self):
        obs = Observability075()
        obs.record_trigger("scheduled", 0.3)
        obs.record_gate("drift_gate", "pass")
        obs.record_completed("promoted", 2.0, 1.0)
        text = obs.export_prometheus()
        assert "uc075_retrain_triggers_total" in text

    def test_loki_and_tempo(self):
        obs = Observability075()
        obs.record_trigger("event_driven", 0.5)
        lines = obs.to_loki_lines()
        assert lines and "uc075_trigger" in lines[0]
        span = obs.to_tempo_spans({"run_id": "r1", "started_at": 1, "finished_at": 2})
        assert span["trace_id"] == "r1"

    def test_dashboard_panels(self):
        dash = Observability075.render_grafana_dashboard()
        assert dash["uid"] == "uc075-cto"
        assert len(dash["panels"]) == 8


# ---------------------------------------------------------------------------
# AuditLog — unitarios
# ---------------------------------------------------------------------------

class TestAuditLog:
    def test_hash_chain_integrity(self):
        from models_075 import AuditRecord
        log = AuditLog()
        log.append(AuditRecord(run_id="r1", action="promote"))
        log.append(AuditRecord(run_id="r2", action="rollback"))
        assert log.verify_chain()
        # tamper
        log._records[0].action = "tampered"
        assert not log.verify_chain()


# ---------------------------------------------------------------------------
# Orquestador — integración
# ---------------------------------------------------------------------------

class TestOrchestratorIntegration:
    def test_full_promote_flow(self):
        orch, events = make_orchestrator()
        run = orch.on_demand(
            "agent-1", "product_change", "new feature",
            new_data=[{"f": i} for i in range(10)],
        )
        assert run.status == PipelineStatus.PROMOTED
        assert run.decision is not None and run.decision.value == "promote"
        assert run.freeze is not None
        assert run.mlflow_run_id
        assert len(events) >= 3  # started + gates + completed

    def test_event_driven_flow(self):
        orch, _ = make_orchestrator()
        run = orch.evaluate_metrics("agent-2", {"drift_score": 0.9, "error_rate": 0.2})
        assert run is not None
        assert run.strategy_used == "event_driven"
        # alto drift (0.9) supera auto_approve_max_risk → requiere HITL
        assert run.status == PipelineStatus.PENDING_HITL

    def test_scheduled_flow(self):
        orch, _ = make_orchestrator()
        run = orch.check_scheduled("agent-3", interval_hours=24)
        assert run is not None
        assert orch.check_scheduled("agent-3", interval_hours=24) is None

    def test_incremental_flow(self):
        orch, _ = make_orchestrator()
        run = orch.incremental_step("agent-4", [{"f": 1}], [{"f": 0}])
        assert run is not None
        assert run.strategy_used == "incremental"

    def test_hilt_resolve_promote(self):
        orch = ContinuousTrainingOrchestrator(
            policy=OrchestratorPolicy(auto_approve_max_risk=0.0),
            trainer=winning_matchup_trainer,
            evaluator=lambda r, c: {"accuracy": c.get("accuracy", 0.8) + 0.05,
                                    "replay_accuracy": 0.9, "out_of_sample": 1},
            hitl_approver=lambda run: None,
            mlflow_enabled=False,
        )
        run = orch.on_demand("agent-5", "policy_change", "finance rule", domain="financial")
        assert run.status == PipelineStatus.PENDING_HITL
        resolved = orch.resolve_hitl(run.run_id, approved=True, approver="legal@utron.ai")
        assert resolved.status == PipelineStatus.PROMOTED
        assert resolved.approval.approver == "legal@utron.ai"

    def test_hilt_resolve_reject(self):
        orch = ContinuousTrainingOrchestrator(
            policy=OrchestratorPolicy(auto_approve_max_risk=0.0),
            trainer=winning_matchup_trainer,
            evaluator=lambda r, c: {"accuracy": c.get("accuracy", 0.8) + 0.05,
                                    "replay_accuracy": 0.9, "out_of_sample": 1},
            hitl_approver=lambda run: None,
            mlflow_enabled=False,
        )
        run = orch.on_demand("agent-6", "policy_change", "legal rule", domain="legal")
        resolved = orch.resolve_hitl(run.run_id, approved=False, approver="risk@utron.ai")
        assert resolved.status == PipelineStatus.REJECTED

    def test_audit_recorded_per_run(self):
        orch, _ = make_orchestrator()
        orch.on_demand("agent-7", "policy_change", "x")
        assert orch.audit.verify_chain()
        records = orch.audit.list()
        assert records
        assert records[-1]["evidence"]["strategy"] == "on_demand"

    def test_event_sink_receives_completion(self):
        orch, events = make_orchestrator()
        orch.on_demand("agent-8", "policy_change", "x")
        kinds = {e["event_type"] for e in events}
        assert "uc075_run_started" in kinds
        assert "uc075_run_completed" in kinds

    def test_dashboard_state(self):
        orch, _ = make_orchestrator()
        orch.on_demand("agent-9", "policy_change", "x")
        state = orch.dashboard_state()
        assert state["runs_total"] == 1
        assert state["audit_chain_valid"]
        assert "scheduled" in state["strategy_support"]
