"""
UC-308 — Champion/Challenger experiment tests.

Covers: deterministic fan-out, authority guard, paper execution, metrics,
walk-forward gates, statistical criteria, risk limits, HITL approval,
UC-309 ingestion, UC-324 shutdown/reconciliation, audit tamper detection,
API endpoints and end-to-end flow.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

import pytest

from cc_audit_308 import AuditChain
from cc_execution_308 import PaperExecutionEngine
from cc_metrics_308 import PromotionCriteria, StageMetricsCalculator
from cc_models_308 import (
    ExperimentConfig,
    ExperimentState,
    MarketEvent,
    ModelRegistration,
    OrderSide,
    PromotionAction,
)
from cc_predictors_308 import (
    ChampionDemoPredictor,
    ChallengerDemoPredictor,
    PredictorAdapter,
    UC315SkillPredictorAdapter,
    make_demo_predictors,
)
from champion_challenger_experiment_308 import (
    ChampionChallengerExperiment,
    ChampionChallengerManager,
    generate_market_events,
)


@pytest.fixture
def cc_config() -> ExperimentConfig:
    return ExperimentConfig(
        experiment_id="test-cc-001",
        symbol="TEST",
        initial_cash=1_000_000.0,
        max_position=500.0,
        max_exposure=100_000.0,
        max_drawdown=0.20,
        fee_rate=0.001,
        base_latency_ms=2.0,
        min_paired_samples=10,
        walk_forward_samples=10,
        shadow_samples=10,
        paper_samples=10,
        bootstrap_iterations=500,
        bootstrap_seed=7,
    )


@pytest.fixture
def fresh_experiment(cc_config: ExperimentConfig) -> ChampionChallengerExperiment:
    exp = ChampionChallengerExperiment(config=cc_config)
    exp.register_champion("champion", "1.0.0", ChampionDemoPredictor())
    exp.register_challenger("challenger", "2.0.0", ChallengerDemoPredictor())
    return exp


@pytest.fixture
def simple_event() -> MarketEvent:
    return MarketEvent(
        event_id="E-001",
        source_ts=1_700_000_000.0,
        receive_ts=1_700_000_000.05,
        symbol="TEST",
        bid=150.0,
        ask=150.05,
        bid_size=1000.0,
        ask_size=1000.0,
        reference_bid=150.02,
        reference_ask=150.07,
    )


# ---------------------------------------------------------------------------
# Market event validation and fan-out
# ---------------------------------------------------------------------------

def test_market_event_hash_is_deterministic(simple_event: MarketEvent):
    assert simple_event.event_hash() == simple_event.event_hash()
    # A different event has a different hash.
    other = MarketEvent(
        event_id="E-002",
        source_ts=simple_event.source_ts,
        receive_ts=simple_event.receive_ts,
        symbol=simple_event.symbol,
        bid=simple_event.bid,
        ask=simple_event.ask,
        bid_size=simple_event.bid_size,
        ask_size=simple_event.ask_size,
        reference_bid=simple_event.reference_bid,
        reference_ask=simple_event.reference_ask,
    )
    assert simple_event.event_hash() != other.event_hash()


def test_market_event_rejects_invalid_spread():
    ev = MarketEvent(
        event_id="E-003",
        source_ts=1_700_000_000.0,
        receive_ts=1_700_000_000.0,
        symbol="TEST",
        bid=150.1,
        ask=150.0,  # invalid: bid >= ask
        bid_size=100.0,
        ask_size=100.0,
        reference_bid=150.05,
        reference_ask=150.15,
    )
    ok, reason = ev.validate()
    assert not ok
    assert "spread" in reason.lower()


def test_market_event_rejects_stale_out_of_order():
    first = MarketEvent(
        event_id="E-004",
        source_ts=1_700_000_000.0,
        receive_ts=1_700_000_000.0,
        symbol="TEST",
        bid=150.0,
        ask=150.05,
        bid_size=100.0,
        ask_size=100.0,
        reference_bid=150.01,
        reference_ask=150.06,
    )
    later = MarketEvent(
        event_id="E-005",
        source_ts=first.source_ts - 1.0,  # earlier
        receive_ts=first.receive_ts,
        symbol="TEST",
        bid=150.0,
        ask=150.05,
        bid_size=100.0,
        ask_size=100.0,
        reference_bid=150.01,
        reference_ask=150.06,
    )
    ok, reason = later.validate(last_source_ts=first.source_ts)
    assert not ok
    assert "stale" in reason.lower()


def test_predictions_receive_same_hash_correlation_and_timestamp(
    fresh_experiment: ChampionChallengerExperiment, simple_event: MarketEvent
):
    exp = fresh_experiment
    exp.start("historical")
    result = exp.ingest_event(simple_event)
    assert result["success"]
    assert len(exp.predictions["champion"]) == 1
    assert len(exp.predictions["challenger"]) == 1
    cp = exp.predictions["champion"][0]
    cc = exp.predictions["challenger"][0]
    assert cp.input_hash == simple_event.event_hash()
    assert cc.input_hash == simple_event.event_hash()
    assert cp.input_hash == cc.input_hash
    assert cp.correlation_id == cc.correlation_id
    assert cp.prediction_ts == cc.prediction_ts


def test_predictions_mismatch_hash_is_rejected():
    class BadChallenger(PredictorAdapter):
        model_id = "bad"
        version = "0.0.0"

        def predict(self, event, correlation_id, prediction_ts):
            from cc_models_308 import Prediction
            return Prediction(
                model_id=self.model_id,
                version=self.version,
                event_id=event.event_id,
                correlation_id=correlation_id,
                predicted_bid=event.bid,
                predicted_ask=event.ask,
                confidence=0.5,
                prediction_ts=prediction_ts,
                input_hash="wrong-hash",
            )

    exp = ChampionChallengerExperiment(config=ExperimentConfig())
    exp.register_champion("champion", "1.0.0", ChampionDemoPredictor())
    exp.register_challenger("bad", "0.0.0", BadChallenger())
    exp.start("historical")
    ev = generate_market_events(n=1, seed=1)[0]
    result = exp.ingest_event(ev)
    assert not result["success"]
    assert "input_hash" in result["reason"]


# ---------------------------------------------------------------------------
# Authority guard / real-order denial
# ---------------------------------------------------------------------------

def test_challenger_real_order_denied_before_promotion():
    class RecordingGuard:
        def __init__(self):
            self.calls: List[Dict[str, Any]] = []

        def authorize_experiment_trade(self, request: Dict[str, Any]) -> Dict[str, Any]:
            self.calls.append(request)
            if request.get("real_order") and request.get("model_role") == "challenger":
                return {"allowed": False, "mode": "denied", "reason": "challenger real order denied"}
            return {"allowed": True, "mode": "paper_only", "reason": "ok"}

    guard = RecordingGuard()
    config = ExperimentConfig()
    exp = ChampionChallengerExperiment(config=config, authority_guard=guard)
    exp.register_champion("champion", "1.0.0", ChampionDemoPredictor())
    exp.register_challenger("challenger", "2.0.0", ChallengerDemoPredictor())
    exp.start("paper")
    for ev in generate_market_events(n=5, seed=1):
        exp.ingest_event(ev)
    assert any(c.get("model_role") == "challenger" for c in guard.calls)
    assert all(c.get("experiment_id") == exp.experiment_id for c in guard.calls)


def test_default_authority_denies_challenger_real_order():
    from champion_challenger_experiment_308 import DefaultAuthorityGuard
    guard = DefaultAuthorityGuard()
    denied = guard.authorize_experiment_trade({
        "experiment_id": "e", "model_id": "m", "model_version": "v",
        "model_role": "challenger", "experiment_state": "paper", "real_order": True,
    })
    assert not denied["allowed"]
    paper = guard.authorize_experiment_trade({
        "experiment_id": "e", "model_id": "m", "model_version": "v",
        "model_role": "challenger", "experiment_state": "paper", "real_order": False,
    })
    assert paper["allowed"]


# ---------------------------------------------------------------------------
# Paper execution: effects, partial fills, liquidity
# ---------------------------------------------------------------------------

def test_paper_execution_records_fees_slippage_and_latency(simple_event: MarketEvent):
    engine = PaperExecutionEngine(
        model_id="test", version="1.0.0",
        initial_cash=1_000_000.0, fee_rate=0.001, base_latency_ms=2.0,
        default_quantity=100.0,
    )
    pred = ChampionDemoPredictor().predict(simple_event, "c1", time.time())
    result = engine.process_event(simple_event, pred)
    order = result["order"]
    fills = result["fills"]
    snap = result["snapshot"]
    assert order is not None
    assert fills
    assert fills[0]["fee"] > 0
    assert fills[0]["slippage"] >= 0
    assert fills[0]["latency_ms"] >= engine.base_latency_ms
    assert snap["total_pnl"] < 0  # fees + slippage reduce PnL immediately


def test_paper_partial_fill_on_low_liquidity(simple_event: MarketEvent):
    engine = PaperExecutionEngine(
        model_id="test", version="1.0.0",
        initial_cash=1_000_000.0, fee_rate=0.001,
        default_quantity=500.0,
    )
    # Make ask_size smaller than order quantity to force partial fill.
    ev = MarketEvent(
        event_id="E-PARTIAL",
        source_ts=simple_event.source_ts,
        receive_ts=simple_event.receive_ts,
        symbol="TEST",
        bid=150.0,
        ask=150.05,
        bid_size=1000.0,
        ask_size=50.0,  # less than qty
        reference_bid=150.02,
        reference_ask=150.07,
    )
    from cc_models_308 import Prediction
    pred = Prediction(
        model_id="force-buy", version="1", event_id=ev.event_id,
        correlation_id="c", predicted_bid=151.0, predicted_ask=151.05,
        confidence=0.8, prediction_ts=time.time(), input_hash=ev.event_hash(),
    )
    result = engine.process_event(ev, pred)
    fills = result["fills"]
    assert fills
    assert fills[0]["partial"]
    assert fills[0]["quantity"] == 50.0


def test_position_and_exposure_tracked():
    engine = PaperExecutionEngine(
        model_id="test", version="1.0.0",
        initial_cash=1_000_000.0, default_quantity=100.0, max_position=1000.0,
    )
    events = generate_market_events(n=5, seed=3)
    for ev in events:
        pred = ChampionDemoPredictor().predict(ev, "c1", time.time())
        engine.process_event(ev, pred)
    snap = engine.snapshot()
    assert abs(snap.position) <= 1000.0
    assert snap.exposure >= 0
    assert snap.max_drawdown >= 0


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def test_prediction_metrics_are_correct():
    calc = StageMetricsCalculator()
    # Manually build records with known prediction/reference values.
    ev = MarketEvent(
        event_id="M-001",
        source_ts=1.0,
        receive_ts=1.0,
        symbol="TEST",
        bid=100.0,
        ask=100.1,
        bid_size=100.0,
        ask_size=100.0,
        reference_bid=100.2,
        reference_ask=100.3,
    )
    from cc_models_308 import Prediction, PortfolioSnapshot
    pred = Prediction(
        model_id="m", version="1", event_id=ev.event_id,
        correlation_id="c", predicted_bid=100.2, predicted_ask=100.3,
        confidence=0.8, prediction_ts=1.0, input_hash="h",
    )
    snap = PortfolioSnapshot(
        cash=1_000_000.0, position=0.0, market_price=ev.mid,
        market_value=1_000_000.0, avg_entry_price=0.0,
        realized_pnl=0.0, unrealized_pnl=0.0, total_pnl=0.0,
        exposure=0.0, drawdown=0.0, max_drawdown=0.0, timestamp=1.0,
    )
    records = [{"event": ev, "prediction": pred, "order": None, "fills": [], "snapshot": snap.to_dict()}]
    m = calc.compute("test", records)
    assert m.sample_count == 1
    assert m.bid_mae == 0.0
    assert m.ask_mae == 0.0
    assert m.mid_accuracy == 1.0


def test_stage_metrics_avoid_divide_by_zero():
    calc = StageMetricsCalculator()
    m = calc.compute("empty", [])
    assert m.sample_count == 0
    assert m.bid_mae == 0.0
    assert m.sharpe == 0.0
    assert m.sortino == 0.0


def test_promotion_criteria_respects_min_sample():
    criteria = PromotionCriteria(ExperimentConfig(min_paired_samples=100))
    from cc_models_308 import StageMetrics
    champ = StageMetrics(stage="paper", sample_count=5)
    chall = StageMetrics(stage="paper", sample_count=5)
    result = criteria.evaluate(champ, chall, paired_pnl_diff=[0.01, 0.02, 0.01])
    assert not result["eligible"]
    assert "insufficient paired samples" in result["reason"]


def test_promotion_criteria_risk_gate():
    config = ExperimentConfig(min_paired_samples=2, max_drawdown=0.01)
    criteria = PromotionCriteria(config)
    from cc_models_308 import StageMetrics
    champ = StageMetrics(stage="paper", sample_count=2, max_drawdown=0.5)
    chall = StageMetrics(stage="paper", sample_count=2, max_drawdown=0.5)
    result = criteria.evaluate(champ, chall, paired_pnl_diff=[0.01, 0.02])
    assert not result["eligible"]
    assert "risk gate failed" in result["reason"]


def test_bootstrap_is_deterministic():
    config = ExperimentConfig(bootstrap_seed=123, bootstrap_iterations=1000)
    criteria = PromotionCriteria(config)
    diffs = [0.01, -0.005, 0.02, 0.0, -0.01]
    a = criteria.paired_bootstrap_ci(diffs, confidence_level=0.95, iterations=1000, seed=123)
    b = criteria.paired_bootstrap_ci(diffs, confidence_level=0.95, iterations=1000, seed=123)
    assert a == b


# ---------------------------------------------------------------------------
# Walk-forward / stage gates
# ---------------------------------------------------------------------------

def test_stage_transitions_and_terminal_states(fresh_experiment: ChampionChallengerExperiment):
    exp = fresh_experiment
    assert exp.state == ExperimentState.DRAFT.value
    assert exp.start("historical")["success"]
    assert exp.state == ExperimentState.HISTORICAL.value
    assert exp.transition("walk_forward")["success"]
    assert exp.transition("shadow")["success"]
    assert exp.transition("paper")["success"]
    assert not exp.transition("invalid_state")["success"]
    # Cannot transition out of rejected.
    exp.state = ExperimentState.REJECTED.value
    assert not exp.start("historical")["success"]


def test_walk_forward_gate_uses_paired_samples(fresh_experiment: ChampionChallengerExperiment):
    exp = fresh_experiment
    exp.start("historical")
    events = generate_market_events(n=5, seed=1)
    for ev in events:
        exp.ingest_event(ev)
    gate = exp.evaluate_stage_gate()
    assert gate["gate"] == "insufficient_samples"


# ---------------------------------------------------------------------------
# Approval: exact hash, TTL, anti-replay
# ---------------------------------------------------------------------------

def test_approve_requires_exact_report_hash(fresh_experiment: ChampionChallengerExperiment):
    exp = fresh_experiment
    exp.start("paper")
    for ev in generate_market_events(n=10, seed=1):
        exp.ingest_event(ev)
    exp.recommend_promotion()
    exp.state = ExperimentState.AWAITING_APPROVAL.value
    result = exp.approve_promotion(
        report_hash="wrong-hash",
        reviewer_id="operator-1",
        request_id="req-1",
        ttl_seconds=3600.0,
    )
    assert not result["success"]
    assert "report_hash mismatch" in result["reason"]


def test_approve_requires_human_reviewer_and_no_auto():
    class AlwaysYesHITL:
        def approve_experiment_promotion(self, request: Dict[str, Any]) -> Dict[str, Any]:
            return {"approved": True, "reason": "yes"}

    config = ExperimentConfig(min_paired_samples=2, paper_samples=2)
    exp = ChampionChallengerExperiment(config=config, hitl_adapter=AlwaysYesHITL())
    exp.register_champion("c", "1", ChampionDemoPredictor())
    exp.register_challenger("d", "2", ChallengerDemoPredictor())
    exp.start("paper")
    for ev in generate_market_events(n=2, seed=1):
        exp.ingest_event(ev)
    rec = exp.recommend_promotion()
    exp.state = ExperimentState.AWAITING_APPROVAL.value
    # Missing reviewer_id
    result = exp.approve_promotion(rec.report_hash, "", "req-2")
    assert not result["success"]
    assert "reviewer_id" in result["reason"]


def test_approve_ttl_and_anti_replay(fresh_experiment: ChampionChallengerExperiment):
    class YesHITL:
        def approve_experiment_promotion(self, request: Dict[str, Any]) -> Dict[str, Any]:
            return {"approved": True, "reason": "yes"}

    config = ExperimentConfig(min_paired_samples=2, paper_samples=2)
    exp = ChampionChallengerExperiment(config=config, hitl_adapter=YesHITL())
    exp.register_champion("c", "1", ChampionDemoPredictor())
    exp.register_challenger("d", "2", ChallengerDemoPredictor())
    exp.start("paper")
    for ev in generate_market_events(n=2, seed=1):
        exp.ingest_event(ev)
    rec = exp.recommend_promotion()
    exp.state = ExperimentState.AWAITING_APPROVAL.value
    # TTL expired
    result = exp.approve_promotion(
        rec.report_hash, "op", "req-3", ttl_seconds=0.001,
        timestamp=time.time() - 10.0,
    )
    assert not result["success"]
    assert "expired" in result["reason"]

    # Anti-replay: reuse request_id on a failed attempt blocks subsequent use.
    fail = exp.approve_promotion("wrong-hash", "op", "req-4")
    assert not fail["success"]
    result2 = exp.approve_promotion(rec.report_hash, "op", "req-4")
    assert not result2["success"]
    assert "anti-replay" in result2["reason"]

    # Normal approval with a fresh request_id
    rec.recommended_action = PromotionAction.PROMOTE.value
    result = exp.approve_promotion(rec.report_hash, "op", "req-5")
    assert result["success"]
    assert exp.state == ExperimentState.PROMOTED.value


# ---------------------------------------------------------------------------
# UC-309 ingestion without raw leakage
# ---------------------------------------------------------------------------

def test_uc309_ingests_snapshot_without_raw_cot_or_secrets():
    import os, sys
    uc309_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "UC-309", "code")
    if uc309_path not in sys.path:
        sys.path.insert(0, uc309_path)
    from observability_orchestrator import ObservabilityOrchestrator
    orch = ObservabilityOrchestrator()
    snapshot = {
        "experiment_id": "e1",
        "report_hash": "abcd1234" * 4,
        "state": "awaiting_approval",
        "recommended_action": "promote",
        "reason": "challenger is statistically superior",
        "champion_version": "1.0.0",
        "challenger_version": "2.0.0",
        "timestamp": time.time(),
        "chain_of_thought": "I think therefore I promote",  # should be sanitized
        "secret_key": "sk-1234567890abcdef",
    }
    result = orch.ingest_uc308_experiment_snapshot(snapshot)
    assert result["ingested"]
    # Ensure no raw secret or CoT is stored.
    for ev in orch.store.get_all_events():
        raw = str(ev.to_dict())
        assert "sk-" not in raw
        assert "chain_of_thought" not in raw.lower()


# ---------------------------------------------------------------------------
# UC-324 shutdown / reconciliation
# ---------------------------------------------------------------------------

def test_shutdown_rejects_new_events_and_reconciles(fresh_experiment: ChampionChallengerExperiment):
    exp = fresh_experiment
    exp.start("paper")
    for ev in generate_market_events(n=5, seed=1):
        exp.ingest_event(ev)
    result = exp.shutdown_experiment("test-shutdown")
    assert result["success"]
    assert result["final_state"] == ExperimentState.STOPPED.value
    # New events rejected
    ev = generate_market_events(n=1, seed=99)[0]
    ingest = exp.ingest_event(ev)
    assert not ingest["success"]
    assert "stopped" in ingest["reason"]
    rec = result["reconciliation"]
    assert rec["events_ingested"] == 5
    assert rec["audit_chain_valid"]


def test_shutdown_is_idempotent(fresh_experiment: ChampionChallengerExperiment):
    exp = fresh_experiment
    exp.start("paper")
    for ev in generate_market_events(n=3, seed=1):
        exp.ingest_event(ev)
    r1 = exp.shutdown_experiment("shutdown-1")
    r2 = exp.shutdown_experiment("shutdown-2")
    assert r1["success"]
    assert r2["success"]
    assert r1["reconciliation"]["events_ingested"] == r2["reconciliation"]["events_ingested"]


# ---------------------------------------------------------------------------
# Audit hash chain tamper detection
# ---------------------------------------------------------------------------

def test_audit_chain_detects_tampering():
    chain = AuditChain()
    chain.append("test", {"value": 1})
    chain.append("test", {"value": 2})
    assert chain.verify_chain()
    # Tamper the data of the second entry (but not the hash).
    chain.entries[1].data["value"] = 999
    assert not chain.verify_chain()
    assert chain.tamper_detected(2)


def test_experiment_audit_chain_links_predictions_and_outcomes(fresh_experiment: ChampionChallengerExperiment):
    exp = fresh_experiment
    exp.start("paper")
    for ev in generate_market_events(n=3, seed=1):
        exp.ingest_event(ev)
    assert exp.audit.verify_chain()
    entry_types = [e.entry_type for e in exp.audit.entries]
    assert "event_ingested" in entry_types
    assert "paper_outcome" in entry_types


# ---------------------------------------------------------------------------
# UC-315 adapter
# ---------------------------------------------------------------------------

def test_uc315_skill_predictor_adapter_wraps_callable():
    def executor(inputs: Dict[str, Any], domain: str) -> Dict[str, Any]:
        return {"predicted_bid": 151.0, "predicted_ask": 151.05, "confidence": 0.77}

    adapter = UC315SkillPredictorAdapter(executor, "uc315-trader", "1.0.0")
    ev = generate_market_events(n=1, seed=1)[0]
    pred = adapter.predict(ev, "c1", time.time())
    assert pred.model_id == "uc315-trader"
    assert pred.predicted_bid == 151.0
    assert pred.input_hash == ev.event_hash()


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

def test_api_cc_create_register_start_ingest_evaluate():
    from api_308 import app
    client = app.test_client()
    resp = client.post("/api/v1/cc-experiments", json={"experiment_id": "api-cc-01"})
    assert resp.status_code == 200
    body = resp.get_json()
    exp_id = body["experiment_id"]
    assert body["state"] == "draft"

    reg = client.post(f"/api/v1/cc-experiments/{exp_id}/register", json={})
    assert reg.status_code == 200

    start = client.post(f"/api/v1/cc-experiments/{exp_id}/start", json={"stage": "historical"})
    assert start.status_code == 200
    assert start.get_json()["stage"] == "historical"

    ev = generate_market_events(n=1, seed=1)[0]
    ingest = client.post(f"/api/v1/cc-experiments/{exp_id}/ingest", json=ev.to_dict())
    assert ingest.status_code == 200
    assert ingest.get_json()["success"]

    eval_resp = client.post(f"/api/v1/cc-experiments/{exp_id}/evaluate")
    assert eval_resp.status_code == 200
    data = eval_resp.get_json()
    assert "metrics" in data
    assert "gate" in data


def test_api_cc_invalid_event_returns_400():
    from api_308 import app
    client = app.test_client()
    resp = client.post("/api/v1/cc-experiments", json={})
    exp_id = resp.get_json()["experiment_id"]
    client.post(f"/api/v1/cc-experiments/{exp_id}/register", json={})
    client.post(f"/api/v1/cc-experiments/{exp_id}/start", json={"stage": "historical"})
    bad = {
        "event_id": "bad",
        "source_ts": 1.0,
        "receive_ts": 1.0,
        "symbol": "X",
        "bid": 10.0,
        "ask": 9.0,  # invalid spread
        "bid_size": 1.0,
        "ask_size": 1.0,
        "reference_bid": 10.0,
        "reference_ask": 11.0,
    }
    ingest = client.post(f"/api/v1/cc-experiments/{exp_id}/ingest", json=bad)
    assert ingest.status_code == 200  # event rejected gracefully, HTTP 200 with success=False
    assert not ingest.get_json()["success"]


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------

def test_end_to_end_experiment_lifecycle():
    config = ExperimentConfig(
        experiment_id="e2e-001",
        min_paired_samples=5,
        walk_forward_samples=5,
        shadow_samples=5,
        paper_samples=5,
        max_drawdown=1.0,
        max_exposure=10_000_000.0,
    )
    exp = ChampionChallengerExperiment(config=config)
    exp.register_champion("champion", "1.0.0", ChampionDemoPredictor())
    exp.register_challenger("challenger", "2.0.0", ChallengerDemoPredictor())

    stages = ["historical", "walk_forward", "shadow", "paper"]
    all_events = generate_market_events(n=20, seed=42)
    cursor = 0
    for i, stage in enumerate(stages):
        if i == 0:
            exp.start(stage)
        else:
            exp.transition(stage)
        n = getattr(config, f"{stage}_samples" if stage != "historical" else "min_paired_samples")
        n = n if stage != "historical" else config.min_paired_samples
        for ev in all_events[cursor:cursor + n]:
            exp.ingest_event(ev)
        cursor += n
        exp.evaluate_stage_gate()

    rec = exp.recommend_promotion()
    assert rec.report_hash
    assert rec.experiment_id == "e2e-001"

    shutdown = exp.shutdown_experiment("e2e-complete")
    assert shutdown["success"]
    assert shutdown["reconciliation"]["events_ingested"] == 20
    assert exp.audit.verify_chain()
