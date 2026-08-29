"""Tests del QualityEvaluator para UC-276."""
from __future__ import annotations

from models import QualityCriteria, QualityLevel, RecursiveVersion
from quality import QualityEvaluator


def _criteria():
    return [
        QualityCriteria(name="clarity", weight=0.25, min_threshold=0.5, target=0.85),
        QualityCriteria(name="conciseness", weight=0.20, min_threshold=0.4, target=0.80),
        QualityCriteria(name="completeness", weight=0.25, min_threshold=0.5, target=0.85),
        QualityCriteria(name="accuracy", weight=0.20, min_threshold=0.6, target=0.90),
        QualityCriteria(name="coherence", weight=0.10, min_threshold=0.5, target=0.80),
    ]


def _evaluator():
    return QualityEvaluator(_criteria())


def test_evaluate_basic():
    ev = _evaluator()
    v = RecursiveVersion.create(iteration=0, content="This is a basic test output.")
    original = "This is a test input with some content to process."
    report = ev.evaluate(v, original)
    assert 0.0 <= report.overall_score <= 1.0
    assert report.quality_level is not None


def test_evaluate_clarity_short_sentences():
    ev = _evaluator()
    content = "Short. Simple. Clear."
    v = RecursiveVersion.create(iteration=0, content=content)
    report = ev.evaluate(v, "original input text")
    assert report.criteria_scores["clarity"] > 0.5


def test_evaluate_conciseness_ideal_ratio():
    ev = _evaluator()
    original = "A" * 100
    content = "B" * 50  # 50% ratio - ideal
    v = RecursiveVersion.create(iteration=0, content=content)
    report = ev.evaluate(v, original)
    assert report.criteria_scores["conciseness"] >= 0.8


def test_evaluate_completeness_overlap():
    ev = _evaluator()
    original = "machine learning algorithms data patterns predictions"
    content = "Machine learning uses algorithms to find patterns in data for predictions"
    v = RecursiveVersion.create(iteration=0, content=content)
    report = ev.evaluate(v, original)
    assert report.criteria_scores["completeness"] > 0.5


def test_evaluate_coherence_with_connectors():
    ev = _evaluator()
    content = "Primero, esto es importante. Además, hay otros factores. Finalmente, la conclusión."
    v = RecursiveVersion.create(iteration=0, content=content)
    report = ev.evaluate(v, "input")
    assert report.criteria_scores["coherence"] > 0.6


def test_evaluate_accuracy_improves_with_iteration():
    ev = _evaluator()
    original = "test input"
    v0 = RecursiveVersion.create(iteration=0, content="Output v0")
    v3 = RecursiveVersion.create(iteration=3, content="Output v3")
    r0 = ev.evaluate(v0, original)
    r3 = ev.evaluate(v3, original)
    assert r3.criteria_scores["accuracy"] >= r0.criteria_scores["accuracy"]


def test_evaluate_returns_quality_report():
    ev = _evaluator()
    v = RecursiveVersion.create(iteration=0, content="Some content here")
    report = ev.evaluate(v, "original")
    assert report.version_id == v.version_id
    assert isinstance(report.criteria_scores, dict)
    assert len(report.criteria_scores) == 5


def test_evaluate_empty_content():
    ev = _evaluator()
    v = RecursiveVersion.create(iteration=0, content="")
    report = ev.evaluate(v, "original input")
    assert report.overall_score < 0.5
