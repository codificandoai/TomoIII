"""Tests del StagnationDetector para UC-276."""
from __future__ import annotations

from stagnation import StagnationDetector


def test_no_stagnation_improving():
    d = StagnationDetector()
    trajectory = [0.5, 0.6, 0.7, 0.8]
    is_stag, reason = d.is_stagnated(trajectory)
    assert is_stag is False


def test_no_stagnation_single_point():
    d = StagnationDetector()
    is_stag, _ = d.is_stagnated([0.5])
    assert is_stag is False


def test_plateau_detected():
    d = StagnationDetector(min_improvement=0.02, max_plateau_iterations=2)
    trajectory = [0.5, 0.51, 0.515, 0.516]
    is_stag, reason = d.is_stagnated(trajectory)
    assert is_stag is True
    assert "Plateau" in reason


def test_degradation_detected():
    d = StagnationDetector(degradation_threshold=0.05)
    trajectory = [0.5, 0.6, 0.7, 0.55]
    is_stag, reason = d.is_stagnated(trajectory)
    assert is_stag is True
    assert "Degradation" in reason


def test_oscillation_detected():
    d = StagnationDetector(window_size=3)
    trajectory = [0.6, 0.62, 0.61, 0.62, 0.61]
    is_stag, reason = d.is_stagnated(trajectory)
    # Plateau may fire before oscillation depending on params
    assert is_stag is True


def test_should_rollback():
    d = StagnationDetector(degradation_threshold=0.05)
    assert d.should_rollback(0.5, 0.6) is True  # dropped by 0.1
    assert d.should_rollback(0.58, 0.6) is False  # small drop


def test_from_config():
    d = StagnationDetector.from_config()
    assert d.min_improvement == 0.02
    assert d.window_size == 3


def test_large_improvement_not_stagnated():
    d = StagnationDetector()
    trajectory = [0.3, 0.5, 0.7, 0.9]
    is_stag, _ = d.is_stagnated(trajectory)
    assert is_stag is False
