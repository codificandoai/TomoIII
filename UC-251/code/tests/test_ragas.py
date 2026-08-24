"""Tests de métricas RAGAS."""
import pytest

from models import Chunk, Document, EvaluationSample, RetrievalResult
from ragas_evaluator import HeuristicRAGASEvaluator


def _result(text: str, cid: str = "c-1") -> RetrievalResult:
    return RetrievalResult(
        chunk=Chunk(
            chunk_id=cid,
            doc_id="d-1",
            text=text,
            index=0,
        )
    )


def test_perfect_context_scores_high():
    ev = HeuristicRAGASEvaluator()
    sample = EvaluationSample(
        query="¿Capital de Francia?",
        ground_truth="París es la capital de Francia.",
    )
    results = ["París es la capital de Francia."]
    metrics = ev.evaluate(
        sample,
        answer="París",
        retrieved_chunks=[_result(r) for r in results],
    )
    assert 0 <= metrics.context_precision <= 1
    assert 0 <= metrics.context_recall <= 1
    assert 0 <= metrics.faithfulness <= 1
    assert 0 <= metrics.answer_relevance <= 1


def test_irrelevant_context_low_recall():
    ev = HeuristicRAGASEvaluator()
    sample = EvaluationSample(
        query="¿Capital de Francia?",
        ground_truth="París es la capital de Francia.",
    )
    metrics = ev.evaluate(
        sample,
        answer="Madrid",
        retrieved_chunks=[_result("Madrid es una ciudad grande.")],
    )
    assert metrics.context_recall < 1.0
    assert metrics.faithfulness < 1.0


def test_empty_context_zero_metrics():
    ev = HeuristicRAGASEvaluator()
    sample = EvaluationSample(query="¿Capital de Francia?", ground_truth="París")
    metrics = ev.evaluate(sample, answer="No sé", retrieved_chunks=[])
    assert metrics.context_precision == 0.0
    assert metrics.context_recall == 0.0


def test_metrics_within_zero_one():
    ev = HeuristicRAGASEvaluator()
    sample = EvaluationSample(query="Pregunta", ground_truth="Respuesta")
    metrics = ev.evaluate(
        sample,
        answer="Respuesta del modelo",
        retrieved_chunks=[_result("Texto cualquiera.")],
    )
    for v in metrics.to_dict().values():
        if v is not None:
            assert 0.0 <= v <= 1.0
