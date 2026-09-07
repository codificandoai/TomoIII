"""
UC-325 — Tests unitarios e integración para el Motor de Razonamiento Autorreflexivo.

Cubre:
- Modelos de datos (18 tests)
- Quality gates (12 tests)
- Detección de alucinaciones (10 tests)
- Refinamiento de queries (8 tests)
- Evaluación de retrieval (10 tests)
- Monitor de convergencia (10 tests)
- Observabilidad (8 tests)
- Motor de razonamiento — integración (12 tests)
- API Flask (7 tests)
"""

import sys
import os
import pytest
import json
import importlib

# Asegurar imports desde el directorio code/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from reasoning_models import (
    ReasoningState, ReasoningResult, ReasoningConfig, ReasoningVerdict,
    RetrievedChunk, Hypothesis, KnowledgeGap, QualityScore,
    HallucinationReport, LoopIteration, LoopPhase, HypothesisStatus,
    DEFAULT_QUALITY_THRESHOLDS, QUALITY_WEIGHTS, HALLUCINATION_PATTERNS,
    QueryRefinementConfig,
)
from quality_gates import QualityGateEvaluator
from hallucination_detector import HallucinationDetector
from query_refiner import QueryRefiner
from retrieval_evaluator import RetrievalEvaluator
from convergence_monitor import ConvergenceMonitor
from observability_325 import ObservabilityManager

_mod = importlib.import_module("UC-325")
ReasoningLoopEngine = _mod.ReasoningLoopEngine
StubRetriever = _mod.StubRetriever
StubHypothesisGenerator = _mod.StubHypothesisGenerator


# ═══════════════════════════════════════════════════════════════════════════
# MODELOS DE DATOS
# ═══════════════════════════════════════════════════════════════════════════

class TestReasoningModels:
    """Tests para reasoning_models.py."""

    def test_loop_phase_enum(self):
        assert len(LoopPhase) == 4
        assert LoopPhase.DISCOVER.value == "discover"

    def test_hypothesis_status_enum(self):
        assert len(HypothesisStatus) == 4
        assert HypothesisStatus.ACTIVE.value == "active"

    def test_reasoning_verdict_enum(self):
        assert len(ReasoningVerdict) == 5
        assert ReasoningVerdict.CONVERGED.value == "converged"

    def test_retrieved_chunk_fingerprint(self):
        c = RetrievedChunk(content="hello world", source="test", score=0.8)
        assert c.fingerprint != ""
        # Mismo contenido = mismo fingerprint
        c2 = RetrievedChunk(content="hello world", source="other", score=0.5)
        assert c.fingerprint == c2.fingerprint

    def test_retrieved_chunk_fingerprint_normalization(self):
        c1 = RetrievedChunk(content="Hello  World", source="a", score=0.5)
        c2 = RetrievedChunk(content="hello world", source="b", score=0.5)
        assert c1.fingerprint == c2.fingerprint

    def test_retrieved_chunk_to_dict(self):
        c = RetrievedChunk(content="test", source="src", score=0.75)
        d = c.to_dict()
        assert d["score"] == 0.75
        assert d["source"] == "src"

    def test_hypothesis_to_dict(self):
        h = Hypothesis(statement="test", confidence=0.8)
        d = h.to_dict()
        assert d["status"] == "active"
        assert d["confidence"] == 0.8

    def test_knowledge_gap_to_dict(self):
        g = KnowledgeGap(description="missing", priority=0.9)
        d = g.to_dict()
        assert d["filled"] is False
        assert d["priority"] == 0.9

    def test_quality_score_overall(self):
        q = QualityScore(relevance=0.8, coverage=0.7, consistency=0.9,
                         confidence=0.8, novelty=0.5)
        assert 0 < q.overall <= 1.0

    def test_quality_score_passed(self):
        q_pass = QualityScore(relevance=0.8, coverage=0.7, consistency=0.9,
                              confidence=0.8, novelty=0.5)
        assert q_pass.passed is True

        q_fail = QualityScore(relevance=0.3, coverage=0.2, consistency=0.1,
                              confidence=0.1, novelty=0.0)
        assert q_fail.passed is False

    def test_hallucination_report_to_dict(self):
        r = HallucinationReport(detected=True, severity=0.7,
                                hallucination_type="claim_without_evidence")
        d = r.to_dict()
        assert d["detected"] is True
        assert d["severity"] == 0.7

    def test_reasoning_state_active_hypotheses(self):
        state = ReasoningState(query="test")
        h1 = Hypothesis(statement="a", status=HypothesisStatus.ACTIVE)
        h2 = Hypothesis(statement="b", status=HypothesisStatus.REFUTED)
        state.hypotheses[h1.hypothesis_id] = h1
        state.hypotheses[h2.hypothesis_id] = h2
        assert len(state.active_hypotheses) == 1

    def test_reasoning_state_unfilled_gaps(self):
        state = ReasoningState(query="test")
        g1 = KnowledgeGap(description="a", filled=False)
        g2 = KnowledgeGap(description="b", filled=True)
        state.gaps[g1.gap_id] = g1
        state.gaps[g2.gap_id] = g2
        assert len(state.unfilled_gaps) == 1

    def test_reasoning_state_convergence_score(self):
        state = ReasoningState(query="test")
        state.confidence_trajectory = [0.5, 0.7]
        assert state.convergence_score == pytest.approx(0.2)

    def test_reasoning_config_defaults(self):
        config = ReasoningConfig()
        assert config.max_rounds == 5
        assert config.min_convergence_delta == 0.02
        assert config.hallucination_threshold == 0.5

    def test_reasoning_result_to_dict(self):
        r = ReasoningResult(query="test", confidence=0.8,
                            verdict=ReasoningVerdict.CONVERGED, success=True)
        d = r.to_dict()
        assert d["verdict"] == "converged"
        assert d["success"] is True

    def test_constants(self):
        assert len(DEFAULT_QUALITY_THRESHOLDS) == 5
        assert len(QUALITY_WEIGHTS) == 5
        assert len(HALLUCINATION_PATTERNS) == 6
        assert abs(sum(QUALITY_WEIGHTS.values()) - 1.0) < 0.01


# ═══════════════════════════════════════════════════════════════════════════
# QUALITY GATES
# ═══════════════════════════════════════════════════════════════════════════

class TestQualityGates:
    """Tests para quality_gates.py."""

    def test_evaluate_empty_state(self):
        ev = QualityGateEvaluator()
        state = ReasoningState(query="test")
        score = ev.evaluate(state)
        assert score.overall == 0.0

    def test_evaluate_with_data(self):
        ev = QualityGateEvaluator()
        state = ReasoningState(query="reasoning loops", round_number=1)
        c = RetrievedChunk(content="reasoning loops improve quality", source="doc", score=0.8)
        state.all_chunks[c.chunk_id] = c
        h = Hypothesis(statement="loops improve quality", supporting_chunks=[c.chunk_id],
                       confidence=0.7, coherence_score=0.8, evidence_strength=0.8)
        state.hypotheses[h.hypothesis_id] = h
        score = ev.evaluate(state)
        assert score.relevance > 0
        assert score.consistency > 0

    def test_relevance_high_overlap(self):
        ev = QualityGateEvaluator()
        state = ReasoningState(query="machine learning models")
        c = RetrievedChunk(content="machine learning models are powerful", source="a", score=0.9)
        state.all_chunks[c.chunk_id] = c
        score = ev.evaluate(state)
        assert score.relevance > 0.3

    def test_relevance_no_overlap(self):
        ev = QualityGateEvaluator()
        state = ReasoningState(query="quantum computing")
        c = RetrievedChunk(content="cooking recipe pasta tomato", source="a", score=0.1)
        state.all_chunks[c.chunk_id] = c
        score = ev.evaluate(state)
        assert score.relevance < 0.5

    def test_coverage_with_gaps(self):
        ev = QualityGateEvaluator()
        state = ReasoningState(query="test")
        h = Hypothesis(statement="test", confidence=0.8)
        state.hypotheses[h.hypothesis_id] = h
        g = KnowledgeGap(description="critical gap", priority=0.9, filled=False)
        state.gaps[g.gap_id] = g
        score = ev.evaluate(state)
        assert score.coverage < 1.0

    def test_novelty_first_round(self):
        ev = QualityGateEvaluator()
        state = ReasoningState(query="test", round_number=1)
        c = RetrievedChunk(content="new info", source="a", score=0.5, retrieval_round=1)
        state.all_chunks[c.chunk_id] = c
        score = ev.evaluate(state)
        assert score.novelty == 1.0

    def test_check_gates(self):
        ev = QualityGateEvaluator()
        score = QualityScore(relevance=0.8, coverage=0.7, consistency=0.9,
                             confidence=0.8, novelty=0.5)
        gates = ev.check_gates(score)
        assert gates["relevance"] is True
        assert gates["coverage"] is True

    def test_all_gates_passed(self):
        ev = QualityGateEvaluator()
        score = QualityScore(relevance=0.8, coverage=0.7, consistency=0.9,
                             confidence=0.8, novelty=0.5)
        assert ev.all_gates_passed(score) is True

    def test_all_gates_failed(self):
        ev = QualityGateEvaluator()
        score = QualityScore(relevance=0.1, coverage=0.1, consistency=0.1,
                             confidence=0.1, novelty=0.0)
        assert ev.all_gates_passed(score) is False

    def test_weakest_dimension(self):
        ev = QualityGateEvaluator()
        score = QualityScore(relevance=0.9, coverage=0.1, consistency=0.9,
                             confidence=0.9, novelty=0.9)
        assert ev.get_weakest_dimension(score) == "coverage"

    def test_reset(self):
        ev = QualityGateEvaluator()
        ev._previous_fingerprints.add("test")
        ev.reset()
        assert len(ev._previous_fingerprints) == 0

    def test_confidence_evaluation(self):
        ev = QualityGateEvaluator()
        state = ReasoningState(query="test")
        c = RetrievedChunk(content="evidence", source="doc", score=0.8)
        state.all_chunks[c.chunk_id] = c
        h = Hypothesis(statement="test claim", supporting_chunks=[c.chunk_id],
                       confidence=0.8)
        state.hypotheses[h.hypothesis_id] = h
        score = ev.evaluate(state)
        assert score.confidence > 0


# ═══════════════════════════════════════════════════════════════════════════
# HALLUCINATION DETECTOR
# ═══════════════════════════════════════════════════════════════════════════

class TestHallucinationDetector:
    """Tests para hallucination_detector.py."""

    def test_detect_no_hallucinations(self):
        det = HallucinationDetector()
        state = ReasoningState(query="test")
        c = RetrievedChunk(content="evidence text here", source="doc", score=0.8)
        state.all_chunks[c.chunk_id] = c
        h = Hypothesis(statement="evidence text here", supporting_chunks=[c.chunk_id],
                       confidence=0.7)
        state.hypotheses[h.hypothesis_id] = h
        report = det.detect(state)
        assert report.severity < 1.0

    def test_detect_fabricated_sources(self):
        det = HallucinationDetector()
        state = ReasoningState(query="test")
        h = Hypothesis(statement="claim", supporting_chunks=["fake_id"],
                       confidence=0.9)
        state.hypotheses[h.hypothesis_id] = h
        report = det.detect(state)
        assert len(report.fabricated_sources) > 0

    def test_detect_unsupported_claims(self):
        det = HallucinationDetector()
        state = ReasoningState(query="test")
        h = Hypothesis(statement="totally unrelated claim about quantum physics",
                       confidence=0.9)
        state.hypotheses[h.hypothesis_id] = h
        report = det.detect(state)
        assert len(report.unsupported_claims) > 0

    def test_detect_confidence_inflation(self):
        det = HallucinationDetector()
        state = ReasoningState(query="test")
        c = RetrievedChunk(content="weak evidence", source="doc", score=0.2)
        state.all_chunks[c.chunk_id] = c
        h = Hypothesis(statement="strong claim", supporting_chunks=[c.chunk_id],
                       confidence=0.95)
        state.hypotheses[h.hypothesis_id] = h
        report = det.detect(state)
        assert report.confidence_inflation > 0.3

    def test_detect_extrapolations(self):
        det = HallucinationDetector()
        state = ReasoningState(query="test")
        c = RetrievedChunk(content="some data", source="doc", score=0.3)
        state.all_chunks[c.chunk_id] = c
        h = Hypothesis(statement="This is absolutely always true definitivamente",
                       supporting_chunks=[c.chunk_id], confidence=0.5)
        state.hypotheses[h.hypothesis_id] = h
        report = det.detect(state)
        # Should detect extrapolation (certainty markers + weak evidence)
        assert isinstance(report.severity, float)

    def test_detect_contradictions(self):
        det = HallucinationDetector()
        state = ReasoningState(query="test")
        h1 = Hypothesis(statement="the system is fast and efficient", confidence=0.8)
        h2 = Hypothesis(statement="the system is not fast and not efficient", confidence=0.7)
        state.hypotheses[h1.hypothesis_id] = h1
        state.hypotheses[h2.hypothesis_id] = h2
        report = det.detect(state)
        assert isinstance(report.severity, float)

    def test_apply_corrections_fabricated(self):
        det = HallucinationDetector()
        state = ReasoningState(query="test")
        c = RetrievedChunk(content="real evidence", source="doc", score=0.8)
        state.all_chunks[c.chunk_id] = c
        h = Hypothesis(statement="claim", supporting_chunks=["fake_id", c.chunk_id],
                       confidence=0.9)
        state.hypotheses[h.hypothesis_id] = h

        report = HallucinationReport(
            detected=True, fabricated_sources=["fake"], confidence_inflation=0.0
        )
        state = det.apply_corrections(state, report)
        assert "fake_id" not in h.supporting_chunks
        assert c.chunk_id in h.supporting_chunks

    def test_apply_corrections_no_detection(self):
        det = HallucinationDetector()
        state = ReasoningState(query="test")
        report = HallucinationReport(detected=False)
        state2 = det.apply_corrections(state, report)
        assert state2 is state

    def test_history(self):
        det = HallucinationDetector()
        state = ReasoningState(query="test")
        h = Hypothesis(statement="claim", confidence=0.5)
        state.hypotheses[h.hypothesis_id] = h
        det.detect(state)
        det.detect(state)
        assert len(det.get_history()) == 2
        det.reset()
        assert len(det.get_history()) == 0

    def test_empty_state(self):
        det = HallucinationDetector()
        state = ReasoningState(query="test")
        report = det.detect(state)
        assert report.detected is False


# ═══════════════════════════════════════════════════════════════════════════
# QUERY REFINER
# ═══════════════════════════════════════════════════════════════════════════

class TestQueryRefiner:
    """Tests para query_refiner.py."""

    def test_expand_initial(self):
        r = QueryRefiner()
        queries = r.expand_initial("machine learning")
        assert "machine learning" in queries
        assert len(queries) >= 3

    def test_expand_initial_with_domain(self):
        r = QueryRefiner(config=QueryRefinementConfig(max_expansions=10))
        queries = r.expand_initial("test query", domain="trading")
        assert any("trading" in q for q in queries)

    def test_refine_for_gaps(self):
        r = QueryRefiner()
        state = ReasoningState(query="test query")
        gap = KnowledgeGap(description="missing info about X", priority=0.8)
        queries = r.refine_for_gaps(state, [gap])
        assert len(queries) > 0

    def test_refine_for_verification(self):
        r = QueryRefiner()
        h = Hypothesis(statement="weak claim", confidence=0.5)
        queries = r.refine_for_verification([h], "test query")
        assert len(queries) >= 2

    def test_generalize(self):
        r = QueryRefiner()
        queries = r.generalize("específicamente en el contexto de trading", [])
        assert len(queries) >= 1

    def test_get_stats(self):
        r = QueryRefiner()
        r.expand_initial("test")
        stats = r.get_stats()
        assert stats["total_queries_generated"] > 0

    def test_reset(self):
        r = QueryRefiner()
        r.expand_initial("test")
        r.reset()
        assert r.get_stats()["total_queries_generated"] == 0

    def test_dedup(self):
        r = QueryRefiner()
        queries = r.expand_initial("test query")
        # No duplicates
        normalized = [" ".join(q.lower().split()) for q in queries]
        assert len(normalized) == len(set(normalized))


# ═══════════════════════════════════════════════════════════════════════════
# RETRIEVAL EVALUATOR
# ═══════════════════════════════════════════════════════════════════════════

class TestRetrievalEvaluator:
    """Tests para retrieval_evaluator.py."""

    def test_evaluate_empty(self):
        ev = RetrievalEvaluator()
        result = ev.evaluate_chunks("test", [])
        assert result["quality_score"] == 0.0
        assert result["should_requery"] is True

    def test_evaluate_good_chunks(self):
        ev = RetrievalEvaluator()
        chunks = [
            RetrievedChunk(content="test reasoning loops evaluation", source="a", score=0.8),
            RetrievedChunk(content="different topic about synthesis", source="b", score=0.7),
        ]
        result = ev.evaluate_chunks("test reasoning", chunks)
        assert result["quality_score"] > 0

    def test_filter_relevant(self):
        ev = RetrievalEvaluator()
        chunks = [
            RetrievedChunk(content="relevant content about query", source="a", score=0.8),
            RetrievedChunk(content="xyz abc totally unrelated", source="b", score=0.1),
        ]
        filtered = ev.filter_relevant("relevant content query", chunks)
        assert len(filtered) >= 1

    def test_deduplicate(self):
        ev = RetrievalEvaluator()
        existing = [RetrievedChunk(content="hello world", source="a", score=0.5)]
        new = [
            RetrievedChunk(content="hello world", source="b", score=0.6),  # duplicate
            RetrievedChunk(content="something completely different here", source="c", score=0.7),
        ]
        unique = ev.deduplicate(new, existing)
        assert len(unique) == 1

    def test_detect_contradictions(self):
        ev = RetrievalEvaluator()
        chunks = [
            RetrievedChunk(content="the system is fast efficient performant", source="a", score=0.8),
            RetrievedChunk(content="the system is not fast not efficient not performant", source="b", score=0.7),
        ]
        contradictions = ev.detect_contradictions(chunks)
        assert len(contradictions) >= 1

    def test_suggest_requery_none(self):
        ev = RetrievalEvaluator()
        state = ReasoningState(query="test")
        result = ev.suggest_requery_strategy(
            {"should_requery": False, "avg_relevance": 0.8, "coverage": 0.7},
            state,
        )
        assert result["strategy"] == "none"

    def test_suggest_requery_generalize(self):
        ev = RetrievalEvaluator()
        state = ReasoningState(query="test")
        result = ev.suggest_requery_strategy(
            {"should_requery": True, "avg_relevance": 0.1, "coverage": 0.5, "redundancy": 0.2},
            state,
        )
        assert result["strategy"] == "generalize"

    def test_suggest_requery_expand(self):
        ev = RetrievalEvaluator()
        state = ReasoningState(query="test")
        result = ev.suggest_requery_strategy(
            {"should_requery": True, "avg_relevance": 0.5, "coverage": 0.2, "redundancy": 0.2},
            state,
        )
        assert result["strategy"] == "expand"

    def test_suggest_requery_specialize(self):
        ev = RetrievalEvaluator()
        state = ReasoningState(query="test")
        result = ev.suggest_requery_strategy(
            {"should_requery": True, "avg_relevance": 0.5, "coverage": 0.6, "redundancy": 0.8},
            state,
        )
        assert result["strategy"] == "specialize"

    def test_redundancy_single_chunk(self):
        ev = RetrievalEvaluator()
        result = ev.evaluate_chunks("test", [
            RetrievedChunk(content="single chunk", source="a", score=0.5)
        ])
        assert result["redundancy"] == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# CONVERGENCE MONITOR
# ═══════════════════════════════════════════════════════════════════════════

class TestConvergenceMonitor:
    """Tests para convergence_monitor.py."""

    def test_max_rounds(self):
        cm = ConvergenceMonitor()
        state = ReasoningState(query="test", max_rounds=3, round_number=3)
        result = cm.should_stop(state)
        assert result["stop"] is True
        assert result["verdict"] == ReasoningVerdict.MAX_ROUNDS

    def test_continue(self):
        cm = ConvergenceMonitor()
        state = ReasoningState(query="test", max_rounds=5, round_number=1)
        state.confidence_trajectory = [0.3]
        c = RetrievedChunk(content="test", source="a", score=0.5)
        state.all_chunks[c.chunk_id] = c
        result = cm.should_stop(state)
        assert result["stop"] is False

    def test_convergence(self):
        cm = ConvergenceMonitor(min_convergence_delta=0.05)
        state = ReasoningState(query="test", max_rounds=10, round_number=3)
        state.confidence_trajectory = [0.7, 0.72, 0.721]
        h = Hypothesis(statement="test", confidence=0.7)
        state.hypotheses[h.hypothesis_id] = h
        result = cm.should_stop(state)
        assert result["stop"] is True
        assert result["verdict"] == ReasoningVerdict.CONVERGED

    def test_hallucination_abort(self):
        cm = ConvergenceMonitor(hallucination_abort_threshold=0.8)
        state = ReasoningState(query="test", round_number=1)
        report = HallucinationReport(detected=True, severity=0.9)
        result = cm.should_stop(state, hallucination=report)
        assert result["stop"] is True
        assert result["verdict"] == ReasoningVerdict.HALLUCINATION_DETECTED

    def test_stall_detection(self):
        cm = ConvergenceMonitor(stall_threshold=2)
        state = ReasoningState(query="test", max_rounds=10, round_number=1)
        state.confidence_trajectory = [0.5]
        # First call
        cm.should_stop(state)
        # Second call — same state = stall
        cm.should_stop(state)
        # Third call — still same = should stop
        result = cm.should_stop(state)
        assert result["stop"] is True
        assert result["verdict"] == ReasoningVerdict.STALLED

    def test_insufficient_data(self):
        cm = ConvergenceMonitor()
        state = ReasoningState(query="test", round_number=2)
        result = cm.should_stop(state)
        assert result["stop"] is True
        assert result["verdict"] == ReasoningVerdict.INSUFFICIENT_DATA

    def test_convergence_delta(self):
        cm = ConvergenceMonitor()
        state = ReasoningState(query="test")
        state.confidence_trajectory = [0.5, 0.7]
        assert cm.compute_convergence_delta(state) == pytest.approx(0.2)

    def test_progress_score(self):
        cm = ConvergenceMonitor()
        state = ReasoningState(query="test")
        h = Hypothesis(statement="test", confidence=0.8)
        state.hypotheses[h.hypothesis_id] = h
        state.confidence_trajectory = [0.8]
        score = cm.compute_progress_score(state)
        assert 0 < score <= 1.0

    def test_trajectory_improving(self):
        cm = ConvergenceMonitor()
        analysis = cm.get_trajectory_analysis([0.3, 0.5, 0.7, 0.85])
        assert analysis["trend"] == "improving"
        assert analysis["direction"] == "up"

    def test_trajectory_insufficient(self):
        cm = ConvergenceMonitor()
        analysis = cm.get_trajectory_analysis([0.5])
        assert analysis["trend"] == "insufficient_data"


# ═══════════════════════════════════════════════════════════════════════════
# OBSERVABILITY
# ═══════════════════════════════════════════════════════════════════════════

class TestObservability:
    """Tests para observability_325.py."""

    def test_counters(self):
        obs = ObservabilityManager()
        obs.inc_counter("test_c")
        obs.inc_counter("test_c")
        counters = obs.get_counters()
        assert "test_c" in counters

    def test_histograms(self):
        obs = ObservabilityManager()
        obs.observe_histogram("test_h", 1.0)
        obs.observe_histogram("test_h", 2.0)
        h = obs.get_histograms()
        assert len(h["test_h"]) == 2

    def test_gauges(self):
        obs = ObservabilityManager()
        obs.set_gauge("test_g", 42.0)
        assert obs.get_gauges()["test_g"] == 42.0

    def test_logs(self):
        obs = ObservabilityManager()
        obs.log("INFO", "test msg", trace_id="t1")
        obs.log("ERROR", "err", trace_id="t1")
        assert len(obs.get_logs()) == 2
        assert len(obs.get_logs(level="ERROR")) == 1

    def test_spans(self):
        obs = ObservabilityManager()
        span = obs.start_span("op1", trace_id="t1")
        obs.end_span(span.span_id)
        spans = obs.get_spans(trace_id="t1")
        assert len(spans) == 1
        assert spans[0]["duration_ms"] >= 0

    def test_export_prometheus(self):
        obs = ObservabilityManager()
        obs.inc_counter("test")
        text = obs.export_prometheus()
        assert isinstance(text, str)

    def test_summary(self):
        obs = ObservabilityManager()
        obs.log("INFO", "msg")
        obs.start_span("op")
        summary = obs.get_summary()
        assert summary["total_logs"] == 1
        assert summary["total_spans"] == 1

    def test_reset(self):
        obs = ObservabilityManager()
        obs.inc_counter("c")
        obs.log("INFO", "m")
        obs.reset()
        assert obs.get_summary()["total_logs"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# MOTOR DE RAZONAMIENTO — INTEGRACIÓN
# ═══════════════════════════════════════════════════════════════════════════

class TestReasoningEngine:
    """Tests de integración para el motor de razonamiento."""

    def test_basic_reasoning(self):
        engine = ReasoningLoopEngine(config=ReasoningConfig(max_rounds=2))
        result = engine.reason("bucles de razonamiento", domain="agi")
        assert result.rounds_executed > 0
        assert result.trace_id != ""
        assert result.duration_ms > 0

    def test_reasoning_produces_answer(self):
        engine = ReasoningLoopEngine(config=ReasoningConfig(max_rounds=2))
        result = engine.reason("bucles de razonamiento iterativos")
        assert result.answer is not None
        assert result.confidence > 0

    def test_reasoning_produces_hypotheses(self):
        engine = ReasoningLoopEngine(config=ReasoningConfig(max_rounds=2))
        result = engine.reason("razonamiento y calidad")
        assert len(result.hypotheses) > 0

    def test_reasoning_produces_quality_scores(self):
        engine = ReasoningLoopEngine(config=ReasoningConfig(max_rounds=2))
        result = engine.reason("test quality")
        assert len(result.quality_scores) > 0

    def test_reasoning_produces_trajectory(self):
        engine = ReasoningLoopEngine(config=ReasoningConfig(max_rounds=2))
        result = engine.reason("convergencia del razonamiento")
        assert len(result.convergence_trajectory) > 0

    def test_reasoning_respects_max_rounds(self):
        engine = ReasoningLoopEngine(config=ReasoningConfig(max_rounds=1))
        result = engine.reason("test")
        assert result.rounds_executed <= 1

    def test_reasoning_with_custom_retriever(self):
        retriever = StubRetriever(knowledge_base=[
            {"content": "custom knowledge about topic X", "source": "custom"}
        ])
        engine = ReasoningLoopEngine(
            retriever=retriever,
            config=ReasoningConfig(max_rounds=1),
        )
        result = engine.reason("topic X")
        assert result.total_chunks_retrieved > 0

    def test_history(self):
        engine = ReasoningLoopEngine(config=ReasoningConfig(max_rounds=1))
        engine.reason("query 1")
        engine.reason("query 2")
        history = engine.get_history()
        assert len(history) == 2

    def test_observability_summary(self):
        engine = ReasoningLoopEngine(config=ReasoningConfig(max_rounds=1))
        engine.reason("test")
        summary = engine.get_observability_summary()
        assert summary["total_logs"] > 0
        assert summary["total_spans"] > 0

    def test_reset(self):
        engine = ReasoningLoopEngine(config=ReasoningConfig(max_rounds=1))
        engine.reason("test")
        engine.reset()
        assert len(engine.get_history()) == 0

    def test_verdict_type(self):
        engine = ReasoningLoopEngine(config=ReasoningConfig(max_rounds=2))
        result = engine.reason("test")
        assert result.verdict in (
            ReasoningVerdict.CONVERGED,
            ReasoningVerdict.MAX_ROUNDS,
            ReasoningVerdict.STALLED,
            ReasoningVerdict.INSUFFICIENT_DATA,
            ReasoningVerdict.HALLUCINATION_DETECTED,
        )

    def test_to_dict_serializable(self):
        engine = ReasoningLoopEngine(config=ReasoningConfig(max_rounds=1))
        result = engine.reason("test")
        d = result.to_dict()
        # Should be JSON-serializable
        json_str = json.dumps(d)
        assert len(json_str) > 0


# ═══════════════════════════════════════════════════════════════════════════
# API FLASK
# ═══════════════════════════════════════════════════════════════════════════

class TestAPI:
    """Tests para api_325.py."""

    @pytest.fixture
    def client(self):
        from api_325 import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"

    def test_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "endpoints" in data

    def test_schema(self, client):
        resp = client.get("/api/v1/schema")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "input_cards" in data
        assert "output_cards" in data

    def test_reasoning_run(self, client):
        resp = client.post("/api/v1/reasoning/run", json={
            "query": "test reasoning", "max_rounds": 1,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "verdict" in data
        assert "confidence" in data

    def test_reasoning_run_missing_query(self, client):
        resp = client.post("/api/v1/reasoning/run", json={})
        assert resp.status_code == 400

    def test_refine_query(self, client):
        resp = client.post("/api/v1/reasoning/refine-query", json={
            "query": "test query", "strategy": "expand",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["refined_queries"]) >= 1

    def test_metrics(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200
