"""Tests del Modelo Causal Simbólico (SCM) y del simulador LLM."""
from __future__ import annotations

import pytest

from causal_model import LLMReasoner, SymbolicCausalModel


def test_add_and_trace():
    scm = SymbolicCausalModel()
    scm.add_dependency("A", "B")
    scm.add_dependency("B", "C")
    scm.set_node_state("A", "FALLO")
    trace = scm.find_symbolic_root_cause("C")
    assert trace == ["C", "B", "A"]


def test_no_cycle_initially():
    scm = SymbolicCausalModel()
    scm.add_dependency("A", "B")
    scm.add_dependency("B", "C")
    assert scm.has_cycle() is False


def test_cycle_detection():
    scm = SymbolicCausalModel()
    scm.add_dependency("A", "B")
    scm.add_dependency("B", "C")
    scm.add_dependency("C", "A")
    assert scm.has_cycle() is True


def test_llm_hypothesis_timeout():
    hyp = LLMReasoner.abstract_hypothesis("ConnectionTimeout with PricingAPI", "")
    assert hyp["proposed_root_cause"] == "TokenSession"
    assert hyp["confidence"] > 0.5


def test_llm_decompose_campaign():
    steps = LLMReasoner.decompose_goal("Planificar campaña de marketing", [])
    assert len(steps) >= 4
