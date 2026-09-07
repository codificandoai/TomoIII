"""
UC-325 — Validación operacional del Motor de Razonamiento Autorreflexivo.

Verifica los 6 procesos principales:
1. Modelo de datos y configuración.
2. Quality gates (5 dimensiones).
3. Detección de alucinaciones.
4. Refinamiento de queries.
5. Motor de razonamiento completo (bucle iterativo).
6. Observabilidad (métricas, logs, spans).
"""

import sys
import os

# Asegurar que el directorio actual está en sys.path
sys.path.insert(0, os.path.dirname(__file__))


def validate_models():
    """Valida modelos de datos y configuración."""
    from reasoning_models import (
        ReasoningState, ReasoningResult, ReasoningConfig, ReasoningVerdict,
        RetrievedChunk, Hypothesis, KnowledgeGap, QualityScore,
        HallucinationReport, LoopIteration, LoopPhase, HypothesisStatus,
        DEFAULT_QUALITY_THRESHOLDS, QUALITY_WEIGHTS, HALLUCINATION_PATTERNS,
    )

    # Verificar enums
    assert len(LoopPhase) == 4
    assert len(HypothesisStatus) == 4
    assert len(ReasoningVerdict) == 5

    # Verificar dataclasses
    chunk = RetrievedChunk(content="test content", source="test", score=0.8)
    assert chunk.fingerprint != ""
    assert chunk.to_dict()["score"] == 0.8

    hyp = Hypothesis(statement="test", confidence=0.7)
    assert hyp.to_dict()["status"] == "active"

    gap = KnowledgeGap(description="missing info", priority=0.8)
    assert gap.to_dict()["filled"] is False

    quality = QualityScore(relevance=0.8, coverage=0.7, consistency=0.9, confidence=0.8, novelty=0.5)
    assert 0 < quality.overall <= 1.0

    report = HallucinationReport(detected=False)
    assert report.to_dict()["severity"] == 0.0

    state = ReasoningState(query="test query")
    assert state.trace_id != ""
    assert state.to_dict()["chunks_total"] == 0

    config = ReasoningConfig()
    assert config.max_rounds == 5
    assert config.hallucination_threshold == 0.5

    result = ReasoningResult(query="test")
    assert result.to_dict()["success"] is False

    # Constantes
    assert len(DEFAULT_QUALITY_THRESHOLDS) == 5
    assert len(QUALITY_WEIGHTS) == 5
    assert len(HALLUCINATION_PATTERNS) == 6

    return True


def validate_quality_gates():
    """Valida quality gates."""
    from quality_gates import QualityGateEvaluator
    from reasoning_models import (
        ReasoningState, RetrievedChunk, Hypothesis, QualityScore,
    )

    evaluator = QualityGateEvaluator()

    # Estado vacío
    state = ReasoningState(query="test query")
    score = evaluator.evaluate(state)
    assert score.overall == 0.0

    # Estado con datos
    chunk = RetrievedChunk(content="test reasoning loops", source="doc", score=0.8)
    state.all_chunks[chunk.chunk_id] = chunk

    hyp = Hypothesis(
        statement="reasoning loops improve quality",
        supporting_chunks=[chunk.chunk_id],
        confidence=0.8,
        coherence_score=0.85,
        evidence_strength=0.8,
    )
    state.hypotheses[hyp.hypothesis_id] = hyp
    state.round_number = 1

    score = evaluator.evaluate(state)
    assert score.relevance > 0
    assert score.coverage > 0
    assert score.consistency > 0

    # Gates check
    gates = evaluator.check_gates(score)
    assert isinstance(gates, dict)
    assert "relevance" in gates

    weakest = evaluator.get_weakest_dimension(score)
    assert weakest in ("relevance", "coverage", "consistency", "confidence", "novelty")

    evaluator.reset()
    return True


def validate_hallucination_detection():
    """Valida detección de alucinaciones."""
    from hallucination_detector import HallucinationDetector
    from reasoning_models import (
        ReasoningState, RetrievedChunk, Hypothesis,
    )

    detector = HallucinationDetector()

    # Sin alucinaciones
    state = ReasoningState(query="test")
    chunk = RetrievedChunk(content="evidence text", source="doc", score=0.8)
    state.all_chunks[chunk.chunk_id] = chunk

    hyp = Hypothesis(
        statement="evidence text supports this",
        supporting_chunks=[chunk.chunk_id],
        confidence=0.7,
    )
    state.hypotheses[hyp.hypothesis_id] = hyp

    report = detector.detect(state)
    assert isinstance(report.severity, float)

    # Con fabricación (chunk inexistente)
    hyp2 = Hypothesis(
        statement="fabricated claim",
        supporting_chunks=["nonexistent_chunk"],
        confidence=0.9,
    )
    state.hypotheses[hyp2.hypothesis_id] = hyp2

    report2 = detector.detect(state)
    assert len(report2.fabricated_sources) > 0

    # Correcciones
    state = detector.apply_corrections(state, report2)

    # Historial
    history = detector.get_history()
    assert len(history) >= 2

    detector.reset()
    return True


def validate_query_refinement():
    """Valida refinamiento de queries."""
    from query_refiner import QueryRefiner

    refiner = QueryRefiner()

    # Expansión inicial
    queries = refiner.expand_initial("bucles de razonamiento", domain="agi")
    assert len(queries) >= 3
    assert "bucles de razonamiento" in queries

    # Generalización
    generalized = refiner.generalize(
        "análisis específicamente en el contexto de trading",
        [],
    )
    assert len(generalized) >= 1

    # Stats
    stats = refiner.get_stats()
    assert stats["total_queries_generated"] > 0

    refiner.reset()
    return True


def validate_reasoning_engine():
    """Valida el motor de razonamiento completo."""
    import importlib
    _mod = importlib.import_module("UC-325")
    ReasoningLoopEngine = _mod.ReasoningLoopEngine

    from reasoning_models import ReasoningConfig, ReasoningVerdict

    engine = ReasoningLoopEngine(
        config=ReasoningConfig(max_rounds=2),
    )

    # Ejecutar razonamiento
    result = engine.reason(
        query="¿Cómo mejoran los bucles de razonamiento la precisión?",
        domain="agi",
    )

    assert result.query != ""
    assert result.trace_id != ""
    assert result.rounds_executed > 0
    assert result.rounds_executed <= 2
    assert isinstance(result.confidence, float)
    assert result.verdict in (
        ReasoningVerdict.CONVERGED,
        ReasoningVerdict.MAX_ROUNDS,
        ReasoningVerdict.STALLED,
    )
    assert result.total_chunks_retrieved > 0
    assert result.duration_ms > 0
    assert len(result.hypotheses) > 0
    assert len(result.quality_scores) > 0
    assert len(result.convergence_trajectory) > 0

    # Historial
    history = engine.get_history()
    assert len(history) == 1

    # Observabilidad
    summary = engine.get_observability_summary()
    assert summary["total_logs"] > 0
    assert summary["total_spans"] > 0

    engine.reset()
    return True


def validate_observability():
    """Valida observabilidad."""
    from observability_325 import ObservabilityManager

    obs = ObservabilityManager()

    # Counters
    obs.inc_counter("test_counter")
    obs.inc_counter("test_counter")
    counters = obs.get_counters()
    assert "test_counter" in counters

    # Histograms
    obs.observe_histogram("test_hist", 1.5)
    obs.observe_histogram("test_hist", 2.5)
    histograms = obs.get_histograms()
    assert "test_hist" in histograms
    assert len(histograms["test_hist"]) == 2

    # Gauges
    obs.set_gauge("test_gauge", 42.0)
    gauges = obs.get_gauges()
    assert gauges["test_gauge"] == 42.0

    # Logs
    obs.log("INFO", "test message", trace_id="trace-1")
    obs.log("ERROR", "error message", trace_id="trace-1")
    logs = obs.get_logs()
    assert len(logs) == 2
    error_logs = obs.get_logs(level="ERROR")
    assert len(error_logs) == 1

    # Spans
    span = obs.start_span("test_op", trace_id="trace-1")
    obs.end_span(span.span_id)
    spans = obs.get_spans(trace_id="trace-1")
    assert len(spans) == 1
    assert spans[0]["duration_ms"] >= 0

    # Export
    prom_text = obs.export_prometheus()
    assert isinstance(prom_text, str)

    # Summary
    summary = obs.get_summary()
    assert summary["total_logs"] == 2
    assert summary["total_spans"] == 1
    assert summary["error_logs"] == 1

    obs.reset()
    assert obs.get_summary()["total_logs"] == 0

    return True


def main():
    """Ejecuta todas las validaciones."""
    print("=" * 70)
    print("UC-325 — Validación Operacional")
    print("=" * 70)

    validations = [
        ("Modelos de datos y configuración", validate_models),
        ("Quality gates (5 dimensiones)", validate_quality_gates),
        ("Detección de alucinaciones", validate_hallucination_detection),
        ("Refinamiento de queries", validate_query_refinement),
        ("Motor de razonamiento (bucle iterativo)", validate_reasoning_engine),
        ("Observabilidad (métricas, logs, spans)", validate_observability),
    ]

    all_ok = True
    for name, fn in validations:
        try:
            result = fn()
            status = "[OK]" if result else "[FAIL]"
            if not result:
                all_ok = False
        except Exception as e:
            status = "[FAIL]"
            all_ok = False
            print(f"  {status} {name}: {e}")
            continue

        print(f"  {status} {name}")

    print("=" * 70)
    if all_ok:
        print("  Todos los 6 procesos están funcionando correctamente.")
    else:
        print("  ALGUNOS PROCESOS FALLARON.")
        sys.exit(1)


if __name__ == "__main__":
    main()
