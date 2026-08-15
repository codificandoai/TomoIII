from chaos_engineering import CHAOS_SCENARIOS, ChaosDrillRunner


def test_run_scenario_passes_for_valid_pipeline(orchestrator):
    runner = ChaosDrillRunner(orchestrator)
    result = runner.run_scenario("pii_leak")
    assert result.scenario == "pii_leak"
    assert result.passed is True
    assert "hitl_gate_triggered_correctly" in result.validated_steps


def test_run_unknown_scenario_raises(orchestrator):
    runner = ChaosDrillRunner(orchestrator)
    import pytest
    with pytest.raises(ValueError):
        runner.run_scenario("does_not_exist")


def test_run_all_executes_every_scenario(orchestrator):
    runner = ChaosDrillRunner(orchestrator)
    results = runner.run_all()
    assert len(results) == len(CHAOS_SCENARIOS)
    assert {r.scenario for r in results} == set(CHAOS_SCENARIOS.keys())


def test_incidents_created_by_drill_are_marked_simulation(orchestrator):
    runner = ChaosDrillRunner(orchestrator)
    result = runner.run_scenario("hallucination_spike")
    incident = orchestrator.get_incident(result.incident_id)
    assert incident.is_simulation is True
