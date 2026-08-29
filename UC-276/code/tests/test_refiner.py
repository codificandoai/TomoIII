"""Tests del Refiner para UC-276."""
from __future__ import annotations

from models import QualityCriteria, QualityLevel, QualityReport, RecursiveVersion, RefinementStrategy
from refiner import Refiner


def _report(issues=None, scores=None):
    return QualityReport(
        version_id="v1", overall_score=0.6, quality_level=QualityLevel.ACCEPTABLE,
        criteria_scores=scores or {"clarity": 0.5, "conciseness": 0.7},
        issues=issues or ["clarity: 0.50 < min 0.60"],
        strengths=[], meets_threshold=False, meets_target=False,
    )


def _version(content="This is a test. It has multiple sentences. The third one is here."):
    return RecursiveVersion.create(iteration=0, content=content)


def test_refine_clarify():
    r = Refiner()
    v = _version("This is a very long sentence that goes on and on for quite a while and should probably be split into multiple shorter sentences for better readability overall.")
    result = r.refine(v, _report(), "task", RefinementStrategy.CLARIFY)
    # Should split long sentences
    assert len(result.split(".")) >= 2


def test_refine_concise():
    r = Refiner()
    content = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
    v = _version(content)
    result = r.refine(v, _report(), "task", RefinementStrategy.CONCISE)
    assert len(result) <= len(content) + 10  # Should be shorter or similar


def test_refine_expand():
    r = Refiner()
    v = _version("Short content.")
    result = r.refine(v, _report(), "summarize data", RefinementStrategy.EXPAND)
    assert len(result) > len(v.content)


def test_refine_restructure():
    r = Refiner()
    v = _version("First point. Second point. Third point.")
    result = r.refine(v, _report(), "task", RefinementStrategy.RESTRUCTURE)
    # Should add connectors
    assert "Primero" in result or "Además" in result or "Finalmente" in result


def test_refine_validate():
    r = Refiner()
    v = _version("Some content to validate.")
    result = r.refine(v, _report(), "task", RefinementStrategy.VALIDATE)
    assert "Verificado" in result


def test_refine_optimize():
    r = Refiner()
    v = _version("Generic content.")
    result = r.refine(v, _report(), "task", RefinementStrategy.OPTIMIZE,
                      {"objective": "clarity"})
    assert "clarity" in result


def test_refine_adapt_audience():
    r = Refiner()
    v = _version("Technical content.")
    result = r.refine(v, _report(), "task", RefinementStrategy.ADAPT_AUDIENCE,
                      {"audience": "executives"})
    assert "executives" in result


def test_select_strategy_attacks_weakest():
    r = Refiner()
    criteria = [
        QualityCriteria(name="clarity", weight=0.5, min_threshold=0.5, target=0.8),
        QualityCriteria(name="conciseness", weight=0.5, min_threshold=0.4, target=0.8),
    ]
    report = QualityReport(
        version_id="v1", overall_score=0.5, quality_level=QualityLevel.ACCEPTABLE,
        criteria_scores={"clarity": 0.4, "conciseness": 0.7},
        issues=["clarity low"], strengths=[], meets_threshold=False, meets_target=False,
    )
    strategy = r.select_strategy(report, criteria, 1)
    assert strategy == RefinementStrategy.CLARIFY


def test_select_strategy_rotates_when_no_issues():
    r = Refiner()
    criteria = [QualityCriteria(name="clarity", weight=1.0, min_threshold=0.3, target=0.8)]
    report = QualityReport(
        version_id="v1", overall_score=0.7, quality_level=QualityLevel.GOOD,
        criteria_scores={"clarity": 0.7},
        issues=[], strengths=[], meets_threshold=True, meets_target=False,
    )
    s0 = r.select_strategy(report, criteria, 0)
    s1 = r.select_strategy(report, criteria, 1)
    s2 = r.select_strategy(report, criteria, 2)
    assert s0 == RefinementStrategy.CLARIFY
    assert s1 == RefinementStrategy.CONCISE
    assert s2 == RefinementStrategy.RESTRUCTURE


def test_get_prompt_for_strategy():
    r = Refiner()
    prompt = r.get_prompt_for_strategy(RefinementStrategy.CLARIFY)
    assert "claro" in prompt or "Reescribe" in prompt


def test_all_strategies_produce_output():
    r = Refiner()
    v = _version()
    report = _report()
    for strategy in RefinementStrategy:
        result = r.refine(v, report, "task", strategy)
        assert len(result) > 0
