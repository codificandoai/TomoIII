"""Tests unitarios para UC-322 — Resolución de Conflictos Multiagente."""
import os
import sys

# Añadir el directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from conflict_models import (
    AgentBelief,
    CNPBid,
    CNPResult,
    Conflict,
    ConflictResolutionResult,
    ConflictSeverity,
    ConflictType,
    Concession,
    EscalationResult,
    EscalationVerdict,
    NegotiationResult,
    ResolutionLevel,
    ResolutionStatus,
    Vote,
    VotingResult,
)
from reputation_system import ReputationSystem, EpisodeRecord, ReputationEntry
from negotiation_engine import NegotiationEngine, NegotiationConfig
from voting_system import VotingSystem, VotingConfig
from cnp_dynamic import DynamicCNP, CNPConfig
from escalation_protocol import EscalationProtocol, EscalationConfig
from duplicate_detection import DuplicateDetection, DeadlockDetector
from observability import ObservabilityManager
from uc322 import ConflictResolutionLayer


# ─── Tests de modelos ─────────────────────────────────────────────────────

class TestConflictModels:
    def test_agent_belief_creation(self):
        b = AgentBelief(agent_id="a1", proposition="BUY", confidence=0.8)
        assert b.agent_id == "a1"
        assert b.confidence == 0.8
        assert b.timestamp > 0

    def test_agent_belief_to_dict(self):
        b = AgentBelief(agent_id="a1", proposition="BUY", confidence=0.8)
        d = b.to_dict()
        assert d["agent_id"] == "a1"
        assert d["confidence"] == 0.8

    def test_concession_delta(self):
        c = Concession(agent_id="a1", original_position=0.8, conceded_position=0.6, reason="test")
        assert abs(c.delta - 0.2) < 1e-9

    def test_conflict_creation(self):
        c = Conflict(
            agents_involved=["a1", "a2"],
            description="test conflict",
        )
        assert c.conflict_id is not None
        assert c.resolution_status == ResolutionStatus.DETECTED
        assert not c.is_resolved

    def test_conflict_to_dict(self):
        c = Conflict(agents_involved=["a1"], description="test")
        d = c.to_dict()
        assert "conflict_id" in d
        assert d["agents_involved"] == ["a1"]

    def test_conflict_duration(self):
        c = Conflict(agents_involved=["a1"])
        assert c.duration >= 0

    def test_negotiation_result(self):
        r = NegotiationResult(conflict_id="c1", round_number=3, agreement_reached=True, agreed_value=0.7)
        d = r.to_dict()
        assert d["agreement_reached"] is True
        assert d["agreed_value"] == 0.7

    def test_vote_creation(self):
        v = Vote(agent_id="a1", option="BUY", weight=0.8, raw_reputation=0.9)
        assert v.weight == 0.8
        assert v.raw_reputation == 0.9

    def test_voting_result(self):
        r = VotingResult(conflict_id="c1", winner="BUY", winner_score=0.7, consensus_reached=True)
        d = r.to_dict()
        assert d["winner"] == "BUY"
        assert d["consensus_reached"] is True

    def test_cnp_bid(self):
        b = CNPBid(agent_id="a1", task_id="t1", bid_score=0.9, confidence=0.8, reputation=0.7, estimated_cost=0.1, estimated_latency_ms=500)
        b.composite_score = 0.85
        d = b.to_dict()
        assert d["composite_score"] == 0.85

    def test_escalation_result(self):
        r = EscalationResult(conflict_id="c1", verdict=EscalationVerdict.PROCEED, decided_by="orchestrator", reasoning="test")
        d = r.to_dict()
        assert d["verdict"] == "proceed"

    def test_conflict_resolution_result(self):
        c = Conflict(agents_involved=["a1"])
        r = ConflictResolutionResult(conflict=c, level_reached=ResolutionLevel.NEGOTIATION, success=True)
        d = r.to_dict()
        assert d["success"] is True
        assert d["level_reached"] == "NEGOTIATION"


# ─── Tests de reputación ──────────────────────────────────────────────────

class TestReputationSystem:
    def test_register_agent(self):
        rs = ReputationSystem()
        rs.register_agent("a1", "trading")
        rep = rs.get_reputation("a1", "trading")
        assert 0.0 <= rep <= 1.0

    def test_initial_reputation(self):
        rs = ReputationSystem()
        rep = rs.get_reputation("new_agent", "trading")
        assert rep == ReputationSystem.BASE_REPUTATION

    def test_record_success_episode(self):
        rs = ReputationSystem()
        rs.record_episode("a1", "t1", success=True, quality=0.9, efficiency=0.8)
        rep = rs.get_reputation("a1")
        assert rep > ReputationSystem.BASE_REPUTATION

    def test_record_failure_episode(self):
        rs = ReputationSystem()
        rs.record_episode("a1", "t1", success=False, quality=0.2, efficiency=0.3)
        rep = rs.get_reputation("a1")
        assert rep < ReputationSystem.BASE_REPUTATION + ReputationSystem.WEIGHT_SUCCESS

    def test_reputation_increases_with_success(self):
        rs = ReputationSystem()
        for i in range(10):
            rs.record_episode("a1", f"t{i}", success=True, quality=0.9, efficiency=0.9)
        rep = rs.get_reputation("a1")
        assert rep > 0.8

    def test_reputation_decreases_with_failures(self):
        rs = ReputationSystem()
        for i in range(10):
            rs.record_episode("a1", f"t{i}", success=False, quality=0.1, efficiency=0.1)
        rep = rs.get_reputation("a1")
        assert rep < 0.5

    def test_weight_belief(self):
        rs = ReputationSystem()
        rs.record_episode("a1", "t1", success=True, quality=0.9, efficiency=0.9)
        belief = AgentBelief(agent_id="a1", proposition="test", confidence=0.8)
        weight = rs.weight_belief(belief)
        assert 0.0 < weight <= 1.0

    def test_ranking(self):
        rs = ReputationSystem()
        rs.record_episode("a1", "t1", success=True, quality=0.9)
        rs.record_episode("a2", "t2", success=False, quality=0.2)
        ranking = rs.get_ranking("trading")
        assert ranking[0]["agent_id"] == "a1"
        assert ranking[0]["reputation"] > ranking[1]["reputation"]

    def test_domain_isolation(self):
        rs = ReputationSystem()
        rs.record_episode("a1", "t1", success=True, quality=0.9, domain="trading")
        rs.record_episode("a1", "t2", success=False, quality=0.1, domain="reservations")
        rep_trading = rs.get_reputation("a1", "trading")
        rep_reservations = rs.get_reputation("a1", "reservations")
        assert rep_trading > rep_reservations

    def test_reset(self):
        rs = ReputationSystem()
        rs.record_episode("a1", "t1", success=True)
        rs.reset()
        assert rs.get_reputation("a1") == ReputationSystem.BASE_REPUTATION


# ─── Tests de negociación ─────────────────────────────────────────────────

class TestNegotiationEngine:
    def test_detect_conflict_yes(self):
        rs = ReputationSystem()
        ne = NegotiationEngine(rs)
        beliefs = [
            AgentBelief(agent_id="a1", proposition="BUY", confidence=0.9),
            AgentBelief(agent_id="a2", proposition="BUY", confidence=0.3),
        ]
        conflict = ne.detect_conflict(beliefs)
        assert conflict is not None
        assert conflict.conflict_type == ConflictType.BELIEF_DISAGREEMENT

    def test_detect_conflict_no(self):
        rs = ReputationSystem()
        ne = NegotiationEngine(rs)
        beliefs = [
            AgentBelief(agent_id="a1", proposition="BUY", confidence=0.6),
            AgentBelief(agent_id="a2", proposition="BUY", confidence=0.55),
        ]
        conflict = ne.detect_conflict(beliefs)
        assert conflict is None

    def test_negotiation_reaches_agreement(self):
        rs = ReputationSystem()
        rs.record_episode("a1", "t1", success=True, quality=0.7)
        rs.record_episode("a2", "t2", success=True, quality=0.7)
        ne = NegotiationEngine(rs, NegotiationConfig(max_rounds=10, agreement_threshold=0.1))
        beliefs = [
            AgentBelief(agent_id="a1", proposition="BUY", confidence=0.7),
            AgentBelief(agent_id="a2", proposition="BUY", confidence=0.5),
        ]
        conflict = ne.detect_conflict(beliefs)
        result = ne.negotiate(conflict)
        # Con suficientes rondas deberían converger
        assert result.remaining_gap < 0.2

    def test_negotiation_no_agreement(self):
        rs = ReputationSystem()
        ne = NegotiationEngine(rs, NegotiationConfig(max_rounds=1, agreement_threshold=0.01))
        beliefs = [
            AgentBelief(agent_id="a1", proposition="BUY", confidence=0.9),
            AgentBelief(agent_id="a2", proposition="BUY", confidence=0.1),
        ]
        conflict = ne.detect_conflict(beliefs)
        result = ne.negotiate(conflict)
        assert not result.agreement_reached

    def test_concessions_made(self):
        rs = ReputationSystem()
        rs.record_episode("a1", "t1", success=True, quality=0.7)
        rs.record_episode("a2", "t2", success=True, quality=0.7)
        ne = NegotiationEngine(rs)
        beliefs = [
            AgentBelief(agent_id="a1", proposition="BUY", confidence=0.9),
            AgentBelief(agent_id="a2", proposition="BUY", confidence=0.3),
        ]
        conflict = ne.detect_conflict(beliefs)
        result = ne.negotiate(conflict)
        assert len(result.concessions) > 0


# ─── Tests de votación ────────────────────────────────────────────────────

class TestVotingSystem:
    def test_voting_with_winner(self):
        rs = ReputationSystem()
        rs.record_episode("a1", "t1", success=True, quality=0.9)
        rs.record_episode("a2", "t2", success=False, quality=0.2)
        vs = VotingSystem(rs)
        conflict = Conflict(agents_involved=["a1", "a2"])
        result = vs.vote(
            conflict,
            options=["BUY", "SELL"],
            agent_preferences={"a1": "BUY", "a2": "SELL"},
            agent_confidence={"a1": 0.9, "a2": 0.3},
        )
        assert result.winner == "BUY"
        assert result.winner_score > 0.5

    def test_voting_consensus_reached(self):
        rs = ReputationSystem()
        for a in ["a1", "a2", "a3"]:
            rs.record_episode(a, "t1", success=True, quality=0.8)
        vs = VotingSystem(rs, VotingConfig(consensus_threshold=0.5))
        conflict = Conflict(agents_involved=["a1", "a2", "a3"])
        result = vs.vote(
            conflict,
            options=["BUY", "SELL"],
            agent_preferences={"a1": "BUY", "a2": "BUY", "a3": "BUY"},
            agent_confidence={"a1": 0.9, "a2": 0.8, "a3": 0.85},
        )
        assert result.consensus_reached
        assert result.winner == "BUY"

    def test_voting_no_consensus(self):
        rs = ReputationSystem()
        vs = VotingSystem(rs, VotingConfig(consensus_threshold=0.9))
        conflict = Conflict(agents_involved=["a1", "a2"])
        result = vs.vote(
            conflict,
            options=["BUY", "SELL"],
            agent_preferences={"a1": "BUY", "a2": "SELL"},
            agent_confidence={"a1": 0.5, "a2": 0.5},
        )
        assert not result.consensus_reached

    def test_reputation_affects_vote_weight(self):
        rs = ReputationSystem()
        rs.record_episode("a1", "t1", success=True, quality=0.9)
        rs.record_episode("a2", "t2", success=False, quality=0.1)
        vs = VotingSystem(rs)
        conflict = Conflict(agents_involved=["a1", "a2"])
        result = vs.vote(
            conflict,
            options=["BUY", "SELL"],
            agent_preferences={"a1": "BUY", "a2": "SELL"},
            agent_confidence={"a1": 0.5, "a2": 0.5},
        )
        # a1 tiene mayor reputación, su voto pesa más
        vote_a1 = [v for v in result.votes if v.agent_id == "a1"][0]
        vote_a2 = [v for v in result.votes if v.agent_id == "a2"][0]
        assert vote_a1.weight > vote_a2.weight


# ─── Tests de CNP dinámico ────────────────────────────────────────────────

class TestDynamicCNP:
    def test_cnp_with_winner(self):
        rs = ReputationSystem()
        rs.record_episode("a1", "t1", success=True, quality=0.9)
        rs.record_episode("a2", "t2", success=False, quality=0.2)
        cnp = DynamicCNP(rs)
        conflict = Conflict(agents_involved=["a1", "a2"])
        bids = [
            {"agent_id": "a1", "bid_score": 0.9, "confidence": 0.85, "estimated_cost": 0.1, "estimated_latency_ms": 500},
            {"agent_id": "a2", "bid_score": 0.5, "confidence": 0.4, "estimated_cost": 0.2, "estimated_latency_ms": 1000},
        ]
        result = cnp.run_bidding(conflict, "task1", bids)
        assert result.winner == "a1"
        assert result.winner_score > 0.5

    def test_cnp_no_winner_below_threshold(self):
        rs = ReputationSystem()
        cnp = DynamicCNP(rs, CNPConfig(min_composite_score=0.99))
        conflict = Conflict(agents_involved=["a1"])
        bids = [
            {"agent_id": "a1", "bid_score": 0.3, "confidence": 0.3, "estimated_cost": 0.5, "estimated_latency_ms": 3000},
        ]
        result = cnp.run_bidding(conflict, "task1", bids)
        assert result.winner is None

    def test_cnp_composite_score(self):
        rs = ReputationSystem()
        rs.record_episode("a1", "t1", success=True, quality=0.9)
        cnp = DynamicCNP(rs)
        conflict = Conflict(agents_involved=["a1"])
        bids = [
            {"agent_id": "a1", "bid_score": 0.8, "confidence": 0.8, "estimated_cost": 0.1, "estimated_latency_ms": 500},
        ]
        result = cnp.run_bidding(conflict, "task1", bids)
        assert result.bids[0].composite_score > 0.5

    def test_cnp_generate_bids_from_beliefs(self):
        rs = ReputationSystem()
        cnp = DynamicCNP(rs)
        conflict = Conflict(
            agents_involved=["a1", "a2"],
            beliefs=[
                AgentBelief(agent_id="a1", proposition="test", confidence=0.8),
                AgentBelief(agent_id="a2", proposition="test", confidence=0.6),
            ],
        )
        bids = cnp.generate_bids_from_beliefs(conflict, "task1")
        assert len(bids) == 2
        assert bids[0]["agent_id"] == "a1"


# ─── Tests de escalación ──────────────────────────────────────────────────

class TestEscalationProtocol:
    def test_escalation_proceed(self):
        ep = EscalationProtocol()
        conflict = Conflict(agents_involved=["a1", "a2"], severity=ConflictSeverity.LOW)
        from conflict_models import NegotiationResult
        neg = NegotiationResult(conflict_id=conflict.conflict_id, round_number=5, agreement_reached=False, remaining_gap=0.1)
        result = ep.escalate(conflict, negotiation_result=neg)
        assert result.verdict == EscalationVerdict.PROCEED

    def test_escalation_stop_critical(self):
        ep = EscalationProtocol()
        conflict = Conflict(agents_involved=["a1"], severity=ConflictSeverity.CRITICAL)
        result = ep.escalate(conflict)
        assert result.verdict == EscalationVerdict.STOP

    def test_escalation_review_high(self):
        ep = EscalationProtocol()
        conflict = Conflict(agents_involved=["a1"], severity=ConflictSeverity.HIGH)
        result = ep.escalate(conflict)
        assert result.verdict == EscalationVerdict.REVIEW

    def test_circuit_breaker(self):
        ep = EscalationProtocol(EscalationConfig(circuit_breaker_threshold=3))
        for i in range(3):
            conflict = Conflict(agents_involved=["a1"], severity=ConflictSeverity.LOW)
            ep.escalate(conflict)
        assert ep.circuit_breaker_open

    def test_circuit_breaker_reset(self):
        ep = EscalationProtocol(EscalationConfig(circuit_breaker_threshold=2))
        for i in range(2):
            conflict = Conflict(agents_involved=["a1"], severity=ConflictSeverity.LOW)
            ep.escalate(conflict)
        assert ep.circuit_breaker_open
        ep.reset_circuit_breaker()
        assert not ep.circuit_breaker_open

    def test_escalation_reassign_with_cnp_winner(self):
        ep = EscalationProtocol()
        conflict = Conflict(agents_involved=["a1", "a2"], severity=ConflictSeverity.MEDIUM)
        from conflict_models import CNPResult
        cnp = CNPResult(conflict_id=conflict.conflict_id, task_id="t1", winner="a1", winner_score=0.8)
        result = ep.escalate(conflict, cnp_result=cnp)
        assert result.verdict == EscalationVerdict.REASSIGN

    def test_escalation_history(self):
        ep = EscalationProtocol()
        conflict = Conflict(agents_involved=["a1"])
        ep.escalate(conflict)
        history = ep.get_history()
        assert len(history) == 1


# ─── Tests de detección de duplicados y deadlocks ─────────────────────────

class TestDuplicateDetection:
    def test_register_task_no_duplicate(self):
        dd = DuplicateDetection()
        registered, conflict = dd.register_task("t1", "a1", "trading", "Comprar AAPL")
        assert registered
        assert conflict is None

    def test_register_task_duplicate(self):
        dd = DuplicateDetection()
        dd.register_task("t1", "a1", "trading", "Comprar AAPL")
        registered, conflict = dd.register_task("t2", "a2", "trading", "Comprar AAPL")
        assert not registered
        assert conflict is not None
        assert conflict.conflict_type == ConflictType.DUPLICATE_WORK

    def test_same_agent_no_duplicate(self):
        dd = DuplicateDetection()
        dd.register_task("t1", "a1", "trading", "Comprar AAPL")
        registered, conflict = dd.register_task("t2", "a1", "trading", "Comprar AAPL")
        assert registered
        assert conflict is None

    def test_different_domain_no_duplicate(self):
        dd = DuplicateDetection()
        dd.register_task("t1", "a1", "trading", "Comprar AAPL")
        registered, conflict = dd.register_task("t2", "a2", "reservations", "Comprar AAPL")
        assert registered

    def test_complete_task(self):
        dd = DuplicateDetection()
        dd.register_task("t1", "a1", "trading", "Comprar AAPL")
        dd.complete_task("t1")
        # Ahora la tarea está completada, no debería ser duplicado
        registered, _ = dd.register_task("t2", "a2", "trading", "Comprar AAPL")
        assert registered

    def test_get_active_tasks(self):
        dd = DuplicateDetection()
        dd.register_task("t1", "a1", "trading", "Comprar AAPL")
        dd.register_task("t2", "a2", "trading", "Vender GOOG")
        active = dd.get_active_tasks()
        assert len(active) == 2


class TestDeadlockDetector:
    def test_no_deadlock(self):
        dd = DeadlockDetector()
        dd.set_waiting("a1", "a2", "t1")
        dd.clear_waiting("a1")
        result = dd.detect_cycle()
        assert result is None

    def test_deadlock_detected(self):
        dd = DeadlockDetector()
        dd.set_waiting("a1", "a2", "t1")
        dd.set_waiting("a2", "a1", "t2")
        result = dd.detect_cycle()
        assert result is not None
        assert set(result.cycle) == {"a1", "a2"}

    def test_no_cycle_in_chain(self):
        dd = DeadlockDetector()
        dd.set_waiting("a1", "a2", "t1")
        dd.set_waiting("a2", "a3", "t2")
        # a3 no espera a nadie → no hay ciclo
        result = dd.detect_cycle()
        assert result is None

    def test_waiting_graph(self):
        dd = DeadlockDetector()
        dd.set_waiting("a1", "a2", "t1")
        graph = dd.get_waiting_graph()
        assert graph == {"a1": "a2"}


# ─── Tests de observabilidad ──────────────────────────────────────────────

class TestObservability:
    def test_start_end_span(self):
        obs = ObservabilityManager()
        span = obs.start_span("test_op", "a1")
        assert span.operation == "test_op"
        obs.end_span(span.span_id)
        spans = obs.get_spans()
        assert len(spans) == 1
        assert spans[0]["end_time"] is not None

    def test_log(self):
        obs = ObservabilityManager()
        obs.log("INFO", "test message", agent_id="a1")
        logs = obs.get_logs()
        assert len(logs) == 1
        assert logs[0]["level"] == "INFO"

    def test_counter(self):
        obs = ObservabilityManager()
        obs.inc_counter("test_counter", labels={"status": "ok"})
        obs.inc_counter("test_counter", labels={"status": "ok"})
        counters = obs.get_counters()
        assert "test_counter" in counters

    def test_histogram(self):
        obs = ObservabilityManager()
        obs.observe_histogram("test_hist", 0.5)
        obs.observe_histogram("test_hist", 1.5)
        hists = obs.get_histograms()
        assert "test_hist" in hists
        assert len(hists["test_hist"]) == 2

    def test_gauge(self):
        obs = ObservabilityManager()
        obs.set_gauge("test_gauge", 42.0)
        gauges = obs.get_gauges()
        assert gauges["test_gauge"] == 42.0

    def test_export_prometheus(self):
        obs = ObservabilityManager()
        obs.inc_counter("test_counter")
        obs.set_gauge("test_gauge", 1.0)
        exported = obs.export_prometheus()
        assert isinstance(exported, str)

    def test_reset(self):
        obs = ObservabilityManager()
        obs.log("INFO", "test")
        obs.inc_counter("c1")
        obs.reset()
        assert len(obs.get_logs()) == 0


# ─── Tests de integración — capa completa ─────────────────────────────────

class TestConflictResolutionLayer:
    def test_resolve_no_conflict(self):
        layer = ConflictResolutionLayer()
        beliefs = [
            AgentBelief(agent_id="a1", proposition="BUY", confidence=0.6),
            AgentBelief(agent_id="a2", proposition="BUY", confidence=0.55),
        ]
        result = layer.resolve(beliefs=beliefs, domain="trading")
        assert result.success
        assert result.level_reached == ResolutionLevel.NEGOTIATION

    def test_resolve_with_negotiation(self):
        layer = ConflictResolutionLayer()
        beliefs = [
            AgentBelief(agent_id="a1", proposition="BUY", confidence=0.7),
            AgentBelief(agent_id="a2", proposition="BUY", confidence=0.5),
        ]
        result = layer.resolve(beliefs=beliefs, domain="trading")
        assert result.success

    def test_resolve_escalates_to_voting(self):
        layer = ConflictResolutionLayer()
        # Posiciones muy distantes para que negociación no llegue a acuerdo
        beliefs = [
            AgentBelief(agent_id="a1", proposition="BUY", confidence=0.95),
            AgentBelief(agent_id="a2", proposition="SELL", confidence=0.05),
        ]
        result = layer.resolve(
            beliefs=beliefs,
            domain="trading",
            options=["BUY", "SELL", "HOLD"],
        )
        # Debe escalar más allá de negociación
        assert result.level_reached.value >= ResolutionLevel.VOTING.value

    def test_resolve_full_escalation(self):
        layer = ConflictResolutionLayer()
        beliefs = [
            AgentBelief(agent_id="a1", proposition="BUY", confidence=0.99),
            AgentBelief(agent_id="a2", proposition="SELL", confidence=0.01),
        ]
        result = layer.resolve(
            beliefs=beliefs,
            domain="trading",
            options=["BUY", "SELL"],
        )
        # Debe llegar al menos a votación
        assert result.level_reached.value >= ResolutionLevel.VOTING.value

    def test_resolution_history(self):
        layer = ConflictResolutionLayer()
        beliefs = [
            AgentBelief(agent_id="a1", proposition="BUY", confidence=0.6),
            AgentBelief(agent_id="a2", proposition="BUY", confidence=0.55),
        ]
        layer.resolve(beliefs=beliefs)
        history = layer.get_resolution_history()
        assert len(history) == 1

    def test_reputation_updates_after_resolution(self):
        layer = ConflictResolutionLayer()
        beliefs = [
            AgentBelief(agent_id="a1", proposition="BUY", confidence=0.7),
            AgentBelief(agent_id="a2", proposition="BUY", confidence=0.5),
        ]
        layer.resolve(beliefs=beliefs)
        # Después de la resolución, los agentes deben tener episodios registrados
        entry = layer.reputation.get_entry("a1", "trading")
        assert entry.total_episodes > 0

    def test_check_duplicate(self):
        layer = ConflictResolutionLayer()
        r1 = layer.check_duplicate("t1", "a1", "trading", "Comprar AAPL")
        assert r1["registered"]
        r2 = layer.check_duplicate("t2", "a2", "trading", "Comprar AAPL")
        assert not r2["registered"]
        assert r2["conflict"] is not None

    def test_check_deadlock_no_deadlock(self):
        layer = ConflictResolutionLayer()
        result = layer.check_deadlock()
        assert not result["deadlock_detected"]

    def test_observability_summary(self):
        layer = ConflictResolutionLayer()
        beliefs = [
            AgentBelief(agent_id="a1", proposition="BUY", confidence=0.7),
            AgentBelief(agent_id="a2", proposition="BUY", confidence=0.5),
        ]
        layer.resolve(beliefs=beliefs)
        summary = layer.get_observability_summary()
        assert "counters" in summary
        assert summary["total_logs"] > 0
        assert summary["total_spans"] > 0

    def test_reset(self):
        layer = ConflictResolutionLayer()
        beliefs = [
            AgentBelief(agent_id="a1", proposition="BUY", confidence=0.7),
            AgentBelief(agent_id="a2", proposition="BUY", confidence=0.5),
        ]
        layer.resolve(beliefs=beliefs)
        layer.reset()
        assert len(layer.get_resolution_history()) == 0


# ─── Tests de API REST ────────────────────────────────────────────────────

class TestAPI:
    @pytest.fixture
    def client(self):
        from api_322 import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

    def test_schema(self, client):
        resp = client.get("/api/v1/schema")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "input_cards" in data
        assert "output_cards" in data

    def test_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "service" in data

    def test_resolve_conflict(self, client):
        resp = client.post("/api/v1/conflicts/resolve", json={
            "beliefs": [
                {"agent_id": "a1", "proposition": "BUY", "confidence": 0.7},
                {"agent_id": "a2", "proposition": "BUY", "confidence": 0.5},
            ],
            "domain": "trading",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "level_reached" in data
        assert "success" in data

    def test_record_reputation(self, client):
        resp = client.post("/api/v1/reputation/record", json={
            "agent_id": "a1",
            "task_id": "t1",
            "success": True,
            "quality": 0.9,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "new_reputation" in data

    def test_reputation_ranking(self, client):
        client.post("/api/v1/reputation/record", json={
            "agent_id": "a1", "task_id": "t1", "success": True, "quality": 0.9,
        })
        resp = client.get("/api/v1/reputation/ranking?domain=trading")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "ranking" in data

    def test_get_reputation(self, client):
        client.post("/api/v1/reputation/record", json={
            "agent_id": "a1", "task_id": "t1", "success": True,
        })
        resp = client.get("/api/v1/reputation/a1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["agent_id"] == "a1"

    def test_check_duplicate(self, client):
        resp = client.post("/api/v1/duplicate/check", json={
            "task_id": "t1",
            "agent_id": "a1",
            "domain": "trading",
            "description": "Comprar AAPL",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["registered"] is True

    def test_check_deadlock(self, client):
        resp = client.post("/api/v1/deadlock/check", json={
            "waiting_graph": {},
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "deadlock_detected" in data

    def test_conflict_history(self, client):
        client.post("/api/v1/conflicts/resolve", json={
            "beliefs": [
                {"agent_id": "a1", "proposition": "BUY", "confidence": 0.6},
                {"agent_id": "a2", "proposition": "BUY", "confidence": 0.55},
            ],
        })
        resp = client.get("/api/v1/conflicts/history")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "history" in data

    def test_circuit_breaker_status(self, client):
        resp = client.get("/api/v1/escalation/circuit-breaker")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "open" in data

    def test_observability_summary(self, client):
        resp = client.get("/api/v1/observability/summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "counters" in data

    def test_observability_logs(self, client):
        resp = client.get("/api/v1/observability/logs")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "logs" in data

    def test_observability_spans(self, client):
        resp = client.get("/api/v1/observability/spans")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "spans" in data

    def test_metrics(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_active_tasks(self, client):
        resp = client.get("/api/v1/tasks/active")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "tasks" in data
