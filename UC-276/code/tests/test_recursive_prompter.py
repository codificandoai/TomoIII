"""Tests del RecursivePrompter y RSILoop para UC-276."""
from __future__ import annotations

from models import QualityCriteria, SessionStatus
from recursive_prompter import RecursivePrompter, RSILoop


def _criteria():
    return [
        QualityCriteria(name="clarity", weight=0.25, min_threshold=0.4, target=0.80),
        QualityCriteria(name="conciseness", weight=0.20, min_threshold=0.3, target=0.75),
        QualityCriteria(name="completeness", weight=0.25, min_threshold=0.4, target=0.80),
        QualityCriteria(name="accuracy", weight=0.20, min_threshold=0.4, target=0.85),
        QualityCriteria(name="coherence", weight=0.10, min_threshold=0.3, target=0.75),
    ]


def _prompter(max_iter=5, target=0.85, min_accept=0.5):
    return RecursivePrompter(
        agent_id="test_agent",
        criteria=_criteria(),
        max_iterations=max_iter,
        target_score=target,
        min_acceptable_score=min_accept,
    )


def test_run_basic():
    p = _prompter()
    session = p.run(
        input_data="Machine learning is a subset of AI that uses data.",
        task_description="Summarize this text",
    )
    assert session.session_id is not None
    assert session.final_score > 0
    assert len(session.versions) >= 1


def test_run_converges_with_low_target():
    p = _prompter(target=0.3)
    session = p.run(
        input_data="Some content to process and generate output from.",
        task_description="Generate summary",
    )
    assert session.status == SessionStatus.CONVERGED


def test_run_max_iterations():
    p = _prompter(max_iter=2, target=0.99)
    session = p.run(
        input_data="Content",
        task_description="Generate perfect output",
    )
    assert session.total_iterations <= 2


def test_run_with_initial_version():
    p = _prompter()
    session = p.run(
        input_data="Original input text for testing",
        task_description="Improve text",
        initial_version="This is my initial draft version.",
    )
    assert session.versions[0].content == "This is my initial draft version."


def test_run_with_context():
    p = _prompter()
    session = p.run(
        input_data="Technical content about ML algorithms",
        task_description="Summarize",
        context={"audience": "executives", "objective": "investment decision"},
    )
    assert session.session_id is not None


def test_run_with_custom_generate():
    p = _prompter()

    def my_gen(input_data, context):
        return f"Custom: {input_data[:20]}"

    session = p.run(
        input_data="Input for custom generator",
        task_description="Custom task",
        generate_fn=my_gen,
    )
    assert "Custom:" in session.versions[0].content


def test_session_has_hash():
    p = _prompter()
    session = p.run(
        input_data="Some test input",
        task_description="Generate",
    )
    assert session.session_hash is not None
    assert len(session.session_hash) == 64


def test_improvement_trajectory():
    p = _prompter(max_iter=3)
    session = p.run(
        input_data="A reasonably long input with multiple concepts and details to cover.",
        task_description="Summarize",
    )
    trajectory = session.improvement_trajectory
    assert len(trajectory) >= 1
    assert all(0.0 <= s <= 1.0 for s in trajectory)


def test_stats_after_runs():
    p = _prompter()
    p.run(input_data="Input 1", task_description="Task 1")
    p.run(input_data="Input 2", task_description="Task 2")
    stats = p.get_stats()
    assert stats["total_sessions"] == 2
    assert stats["avg_score"] > 0


def test_stats_empty():
    p = _prompter()
    stats = p.get_stats()
    assert stats["total_sessions"] == 0
    assert stats["avg_score"] == 0.0


# ============================================================
# RSI Loop tests
# ============================================================

def test_rsi_basic():
    rsi = RSILoop(agent_id="test_rsi", max_cycles=3)
    result = rsi.run_cycle(
        task="Improve this text",
        current_output="A simple text to improve iteratively.",
    )
    assert "final_score" in result
    assert "baseline_score" in result
    assert result["cycles_run"] > 0


def test_rsi_improvement():
    rsi = RSILoop(agent_id="test_rsi", max_cycles=5, improvement_threshold=0.01)
    result = rsi.run_cycle(
        task="Optimize output",
        current_output="Basic content that needs improvement over multiple cycles.",
    )
    assert result["final_score"] >= result["baseline_score"]


def test_rsi_history():
    rsi = RSILoop(agent_id="test_rsi")
    rsi.run_cycle(task="Task 1", current_output="Output 1")
    rsi.run_cycle(task="Task 2", current_output="Output 2")
    assert len(rsi.history) == 2


def test_rsi_custom_evaluate():
    def always_high(output):
        return 0.95

    rsi = RSILoop(agent_id="test_rsi", max_cycles=3)
    result = rsi.run_cycle(
        task="Easy task",
        current_output="Already good output",
        evaluate_fn=always_high,
    )
    assert result["baseline_score"] == 0.95


def test_rsi_logic_version_increments():
    rsi = RSILoop(agent_id="test_rsi", max_cycles=5, improvement_threshold=0.01)
    result = rsi.run_cycle(
        task="Iterate",
        current_output="Content to iterate on repeatedly for testing logic version.",
    )
    if result["accepted_changes"] > 0:
        assert result["logic_version"] > 0
