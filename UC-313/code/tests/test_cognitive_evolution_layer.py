"""Tests de la capa de plasticidad sináptica digital UC-313."""
from __future__ import annotations

import pytest

from cognitive_evolution_layer import (
    AdjustmentType,
    ExecutionObservation,
    PlasticityDecision,
    UC307CognitiveEvolutionLayer,
)


@pytest.fixture
def layer():
    return UC307CognitiveEvolutionLayer()


def test_compute_quality_and_efficiency(layer):
    obs = ExecutionObservation(
        agent_id="a",
        success=True,
        confidence=0.9,
        coherence=0.8,
        tokens_used=500,
        tool_calls=2,
        latency_seconds=0.5,
    )
    q = layer._compute_quality(obs)
    e = layer._compute_efficiency(obs)
    assert 0.0 <= q <= 1.0
    assert 0.0 <= e <= 1.0
    assert q > 0.5
    assert e > 0.5


def test_fitness_elite(layer):
    obs = ExecutionObservation(
        agent_id="elite",
        success=True,
        confidence=0.95,
        coherence=0.95,
        tokens_used=100,
        tool_calls=1,
        latency_seconds=0.1,
    )
    result = layer.evaluate_execution(obs)
    assert result.fitness >= layer.config["thresholds"]["fitness_elite"]
    assert result.decision == PlasticityDecision.PERSIST


def test_meta_network_detects_anomaly(layer):
    obs = ExecutionObservation(
        agent_id="bad",
        success=False,
        errors=3,
        tool_calls=4,
        confidence=0.2,
        coherence=0.1,
        tokens_used=12000,
    )
    meta = layer.observe_execution_network(obs)
    assert meta.verdict in {"stop", "review"}
    assert meta.anomalies


def test_proposal_requires_approval(layer):
    prop = layer.propose_adjustment(
        AdjustmentType.ARCHITECTURE,
        target="model",
        change={"new_layer": True},
        reason="Probar nueva arquitectura",
        risk_level="high",
    )
    assert prop.status.value == "awaiting_approval"
    result = layer.apply_proposal(prop.proposal_id, approved=False)
    assert result["status"] == "awaiting_approval"


def test_low_fitness_eliminate(layer):
    obs = ExecutionObservation(
        agent_id="doomed",
        success=False,
        confidence=0.1,
        coherence=0.1,
        tokens_used=2500,
        tool_calls=5,
        latency_seconds=5.0,
    )
    result = layer.evaluate_execution(obs)
    assert result.decision == PlasticityDecision.ELIMINATE or PlasticityDecision.ELIMINATE in result.actions


def test_synaptic_weights_update(layer):
    w1 = layer.update_synaptic_weights("strategy_a", True, 0.9)
    w2 = layer.update_synaptic_weights("strategy_a", False, 0.9)
    assert w1 > 1.0
    assert w2 < w1


def test_rollback(layer):
    # Crear una propuesta y aplicarla para generar snapshot
    prop = layer.propose_adjustment(
        AdjustmentType.PARAM,
        target="x",
        change={"value": 0.99},
        reason="Ajuste de prueba",
        risk_level="low",
    )
    layer.apply_proposal(prop.proposal_id, approved=True, approved_by="test_supervisor")
    # Aplicar alteración posterior
    layer.update_synaptic_weights("x", True, 1.0)
    result = layer.rollback_last_applied()
    assert result["restored"] is True


def test_homeostasis_detects_too_many_adjustments(layer):
    for _ in range(25):
        layer.decision_log.append({
            "trace_id": "t",
            "decision": "adjust_params",
            "fitness": 0.5,
            "agent_id": "a",
        })
    report = layer.check_homeostasis()
    assert report.stable is False
    assert any("Demasiados" in w for w in report.warnings)
