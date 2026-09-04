"""Tests unitarios de operadores evolutivos y población de agentes."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_evolution import AgentPopulation, DNAOperators
from models import AgentDNA, DecisionAction


def test_default_dna_has_required_params():
    ops = DNAOperators()
    dna = ops.default_dna("agent_x")
    assert dna.agent_id == "agent_x"
    assert dna.version == 1
    assert "temperature" in dna.hyperparams
    assert "learning_rate" in dna.hyperparams


def test_mutation_changes_params_and_bumps_version():
    ops = DNAOperators()
    dna = ops.default_dna("agent_x")
    mutated = ops.mutate(dna)
    assert mutated.agent_id == dna.agent_id
    assert mutated.version == dna.version + 1
    assert dna.agent_id in mutated.parent_ids


def test_crossover_inherits_from_parents():
    ops = DNAOperators()
    parent_a = ops.default_dna("a")
    parent_b = ops.default_dna("b")
    child = ops.crossover(parent_a, parent_b)
    assert child.agent_id.startswith("child_")
    assert parent_a.agent_id in child.parent_ids
    assert parent_b.agent_id in child.parent_ids
    assert child.hyperparams


def test_adjust_params_returns_new_version():
    ops = DNAOperators()
    dna = ops.default_dna("agent_z")
    adjusted = ops.adjust_params(dna, reason="calidad baja")
    assert adjusted.version == dna.version + 1
    assert adjusted.hyperparams["temperature"] <= dna.hyperparams["temperature"]


def test_population_register_and_eliminate():
    pop = AgentPopulation()
    dna = DNAOperators().default_dna("x")
    pop.register(dna)
    assert pop.size() == 1
    assert pop.eliminate("x") is True
    assert pop.size() == 0
    assert pop.eliminate("x") is False


def test_evolve_one_mutate():
    pop = AgentPopulation()
    dna = DNAOperators().default_dna("x")
    pop.register(dna)
    new = pop.evolve_one("x", DecisionAction.MUTATE)
    assert new is not None
    assert new.version > dna.version
    assert pop.get("x") == new
