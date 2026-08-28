"""Tests de Nash Bargaining, Pareto, Kalai-Smorodinsky y Weighted Utilitarian."""
from __future__ import annotations

from models import AgentUtilityProfile
from nash_solver import NashBargainingSolver


def _flight_profiles() -> list[AgentUtilityProfile]:
    return [
        AgentUtilityProfile(
            agent_id="user_proxy",
            option_utilities={"AA1234": 8.5, "IB5678": 5.0, "UX9012": 7.5, "AF3456": 9.0},
            disagreement_point=3.0,
        ),
        AgentUtilityProfile(
            agent_id="budget_agent",
            option_utilities={"AA1234": 4.0, "IB5678": 9.0, "UX9012": 7.0, "AF3456": 2.0},
            disagreement_point=2.0,
        ),
        AgentUtilityProfile(
            agent_id="sustain_agent",
            option_utilities={"AA1234": 6.0, "IB5678": 4.0, "UX9012": 9.0, "AF3456": 5.0},
            disagreement_point=2.0,
        ),
    ]


def test_nash_selects_ux9012() -> None:
    solver = NashBargainingSolver(_flight_profiles())
    best, utils, product = solver.solve()
    assert best == "UX9012"
    assert product > 0
    assert len(utils) == 3


def test_pareto_frontier_contains_non_dominated() -> None:
    solver = NashBargainingSolver(_flight_profiles())
    pareto = solver.pareto_frontier()
    assert len(pareto) >= 2
    options = {o for o, _ in pareto}
    assert "UX9012" in options


def test_kalai_smorodinsky() -> None:
    solver = NashBargainingSolver(_flight_profiles())
    best, utils = solver.kalai_smorodinsky()
    assert best is not None
    assert len(utils) == 3


def test_weighted_utilitarian() -> None:
    solver = NashBargainingSolver(_flight_profiles())
    best, utils, wsum = solver.weighted_utilitarian()
    assert best is not None
    assert wsum > 0


def test_weighted_utilitarian_respects_weights() -> None:
    profiles = [
        AgentUtilityProfile(agent_id="a", option_utilities={"X": 10.0, "Y": 1.0}, disagreement_point=0.0, weight=10.0),
        AgentUtilityProfile(agent_id="b", option_utilities={"X": 1.0, "Y": 10.0}, disagreement_point=0.0, weight=1.0),
    ]
    solver = NashBargainingSolver(profiles)
    best, _, _ = solver.weighted_utilitarian()
    assert best == "X"  # Agent a has 10x weight


def test_solve_all_returns_equilibrium_result() -> None:
    solver = NashBargainingSolver(_flight_profiles())
    result = solver.solve_all()
    assert result.best_option == "UX9012"
    assert result.nash_product is not None
    assert len(result.pareto_frontier) >= 2


def test_infeasible_returns_none() -> None:
    profiles = [
        AgentUtilityProfile(agent_id="a", option_utilities={"X": 1.0}, disagreement_point=5.0),
        AgentUtilityProfile(agent_id="b", option_utilities={"X": 1.0}, disagreement_point=5.0),
    ]
    solver = NashBargainingSolver(profiles)
    best, _, product = solver.solve()
    assert best is None
