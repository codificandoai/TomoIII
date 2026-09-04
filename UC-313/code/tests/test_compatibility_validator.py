"""Tests del validador de compatibilidad del stack AGI UC-313."""
from __future__ import annotations

from compatibility_validator import AGICompatibilityValidator


def test_full_stack_compatible():
    validator = AGICompatibilityValidator()
    report = validator.validate()
    assert report["status"] == "compatible"
    assert report["passed"] == report["total"]
    assert all(d["status"] == "ok" for d in report["details"])


def test_self_awareness_blocked_status_handled():
    from self_awareness_loop import SelfAwarenessLoop
    loop = SelfAwarenessLoop()
    ep = loop.run_episode(symbol="AAPL", n_ticks=30, run_cnp=False, run_curiosity=False)
    assert ep.narrative
    assert "Yo observé" in ep.narrative


def test_cnp_empty_agents_graceful():
    from cnp_broadcast_middleware import ContractNetMiddleware
    cnp = ContractNetMiddleware(agents=[])
    out = cnp.run_round("t_empty", "empty task", execution_success=False)
    assert out["round"]["status"] == "completed"
    assert out["round"]["winner_id"] is None


def test_evolution_with_central_brain_prefrontal():
    from central_brain import CentralBrain
    from cognitive_evolution_layer import UC307CognitiveEvolutionLayer
    from config import get_config
    brain = CentralBrain(get_config())
    layer = UC307CognitiveEvolutionLayer(central_brain=brain)
    assert layer.prefrontal is not None
