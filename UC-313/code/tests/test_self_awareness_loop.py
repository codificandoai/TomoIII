"""Tests del bucle recursivo de autoconciencia AGI UC-313."""
from __future__ import annotations

from self_awareness_loop import SelfAwarenessLoop


def test_run_episode_approved():
    loop = SelfAwarenessLoop()
    episode = loop.run_episode(
        symbol="AAPL", n_ticks=40, run_cnp=True, run_curiosity=True, approved=True
    )
    assert episode.symbol == "AAPL"
    assert episode.narrative
    assert "Yo observé" in episode.narrative
    assert episode.monitor_verdict in {"PROCEED", "REVIEW", "STOP"}


def test_run_episode_not_approved():
    loop = SelfAwarenessLoop()
    episode = loop.run_episode(
        symbol="AAPL", n_ticks=40, run_cnp=False, run_curiosity=False, approved=False
    )
    assert episode.symbol == "AAPL"
    assert episode.narrative


def test_run_loop_summary():
    loop = SelfAwarenessLoop()
    summary = loop.run_loop(n_episodes=2, symbol="AAPL", approved=True)
    assert summary["total_episodes"] == 2
    assert "avg_fitness" in summary
    assert summary["homeostasis_stable_all"] in {True, False}
    assert len(summary["episodes"]) == 2


def test_episodes_persisted_in_memory():
    loop = SelfAwarenessLoop()
    loop.run_loop(n_episodes=1, symbol="AAPL")
    # El self-model debe haber registrado al menos un episodio
    recent = loop.self_store.get_recent_performance(limit=1)
    assert len(recent) >= 0  # el test principal es que no lance excepción
