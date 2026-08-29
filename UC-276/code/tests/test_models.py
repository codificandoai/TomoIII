"""Tests de modelos para UC-276."""
from __future__ import annotations

from models import (
    QualityCriteria,
    QualityLevel,
    QualityReport,
    RecursiveSession,
    RecursiveVersion,
    RefinementStrategy,
    SessionStatus,
)


def test_quality_level_values():
    assert QualityLevel.OUTSTANDING.value == "outstanding"
    assert QualityLevel.UNACCEPTABLE.value == "unacceptable"


def test_refinement_strategy_values():
    assert RefinementStrategy.CLARIFY.value == "clarify"
    assert RefinementStrategy.ADAPT_AUDIENCE.value == "adapt_audience"
    assert len(RefinementStrategy) == 8


def test_quality_criteria_creation():
    c = QualityCriteria(name="clarity", weight=0.25, min_threshold=0.5, target=0.85)
    assert c.name == "clarity"
    assert c.weight == 0.25


def test_quality_report_from_scores():
    criteria = [
        QualityCriteria(name="clarity", weight=0.5, min_threshold=0.5, target=0.8),
        QualityCriteria(name="accuracy", weight=0.5, min_threshold=0.6, target=0.9),
    ]
    report = QualityReport.from_scores("v1", criteria, {"clarity": 0.9, "accuracy": 0.95})
    assert report.overall_score >= 0.9
    assert report.quality_level in (QualityLevel.EXCELLENT, QualityLevel.OUTSTANDING)
    assert report.meets_threshold is True
    assert report.meets_target is True


def test_quality_report_issues():
    criteria = [
        QualityCriteria(name="clarity", weight=0.5, min_threshold=0.6, target=0.8),
        QualityCriteria(name="accuracy", weight=0.5, min_threshold=0.7, target=0.9),
    ]
    report = QualityReport.from_scores("v1", criteria, {"clarity": 0.4, "accuracy": 0.5})
    assert len(report.issues) == 2
    assert report.meets_threshold is False


def test_quality_report_classify_levels():
    assert QualityReport._classify_level(0.96) == QualityLevel.OUTSTANDING
    assert QualityReport._classify_level(0.90) == QualityLevel.EXCELLENT
    assert QualityReport._classify_level(0.75) == QualityLevel.GOOD
    assert QualityReport._classify_level(0.55) == QualityLevel.ACCEPTABLE
    assert QualityReport._classify_level(0.35) == QualityLevel.POOR
    assert QualityReport._classify_level(0.1) == QualityLevel.UNACCEPTABLE


def test_recursive_version_create():
    v = RecursiveVersion.create(iteration=0, content="Hello world")
    assert v.iteration == 0
    assert v.content == "Hello world"
    assert len(v.content_hash) == 16
    assert len(v.version_id) == 12


def test_recursive_version_hash_consistency():
    v1 = RecursiveVersion.create(iteration=0, content="Same content")
    v2 = RecursiveVersion.create(iteration=1, content="Same content")
    assert v1.content_hash == v2.content_hash


def test_recursive_version_different_content():
    v1 = RecursiveVersion.create(iteration=0, content="Content A")
    v2 = RecursiveVersion.create(iteration=0, content="Content B")
    assert v1.content_hash != v2.content_hash


def test_recursive_session_creation():
    s = RecursiveSession(agent_id="test", task_description="task", initial_input="input")
    assert len(s.session_id) == 16
    assert s.status == SessionStatus.RUNNING


def test_recursive_session_final_version():
    v = RecursiveVersion.create(iteration=0, content="test")
    s = RecursiveSession(
        agent_id="test", task_description="task", initial_input="input",
        versions=[v], final_version_id=v.version_id,
    )
    assert s.final_version == v


def test_recursive_session_compute_hash():
    v = RecursiveVersion.create(iteration=0, content="test")
    s = RecursiveSession(
        agent_id="test", task_description="task", initial_input="input",
        versions=[v],
    )
    h = s.compute_hash()
    assert len(h) == 64


def test_session_status_values():
    assert SessionStatus.CONVERGED.value == "converged"
    assert SessionStatus.STAGNATED.value == "stagnated"
