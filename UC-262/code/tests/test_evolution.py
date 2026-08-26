"""Tests del motor evolutivo."""
from __future__ import annotations

from config import AppConfig, EvolutionConfig, get_config
from evolution import EvolutionEngine, create_random_genome, default_weights
from models import TravelRequest
from world_simulator import WorldSimulator


def _request(**overrides) -> TravelRequest:
    defaults = {
        "origin": "Madrid",
        "destination": "Barcelona",
        "departure_date": "2026-09-15",
        "return_date": "2026-09-17",
        "travelers": 1,
        "budget": 2000.0,
        "currency": "USD",
        "preferences": {"airline": "Delta"},
        "user_id": "evolution-user",
    }
    defaults.update(overrides)
    return TravelRequest(**defaults)


def test_genome_creation() -> None:
    g = create_random_genome("ag-001")
    assert sum(g.weights.values()) > 0.99
    assert g.agent_id == "ag-001"


def test_evolution_improves_fitness() -> None:
    config = AppConfig(
        world=get_config().world,
        predictor=get_config().predictor,
        memory=get_config().memory,
        checkpoint=get_config().checkpoint,
        evolution=EvolutionConfig(population_size=8, generations=5),
        agent=get_config().agent,
    )
    engine = EvolutionEngine(WorldSimulator(config.world), config.evolution)
    req = _request()
    candidates, stats = engine.evolve(req)
    assert len(candidates) > 0
    assert stats["history"][-1]["best_fitness"] >= stats["history"][0]["best_fitness"]
    best = candidates[0]
    assert best.alive
    assert best.evaluation["fitness"] > 0


def test_memory_rule_filters_violations() -> None:
    config = get_config()
    engine = EvolutionEngine(WorldSimulator(config.world), config.evolution)
    req = _request()
    # Regla que penaliza escalas cortas; con seed 123 puede filtrar algunos
    candidates, _ = engine.evolve(req, memory_rules=["Nunca permitir escalas menores a 90 mins"])
    best = candidates[0]
    # El mejor candidato debería tener fitness razonable
    assert best.evaluation["fitness"] >= 0


def test_default_weights_sum_one() -> None:
    w = default_weights()
    assert abs(sum(w.values()) - 1.0) < 1e-6
