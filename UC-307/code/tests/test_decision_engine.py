"""Tests unitarios del motor de decisiones de UC-307."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decision_engine import DecisionEngine
from models import DecisionAction


def test_eliminate_when_critical():
    engine = DecisionEngine()
    verdict, actions, reason = engine.decide(
        success_rate=0.2,
        normalized_quality=0.1,
        efficiency_score=0.1,
        fitness=0.1,
        population_size=5,
    )
    assert verdict == DecisionAction.ELIMINATE
    assert DecisionAction.ELIMINATE in actions


def test_eliminate_triggers_growth_when_population_low():
    engine = DecisionEngine()
    verdict, actions, reason = engine.decide(
        success_rate=0.2,
        normalized_quality=0.1,
        efficiency_score=0.1,
        fitness=0.1,
        population_size=2,
    )
    assert DecisionAction.ELIMINATE in actions
    assert DecisionAction.GROW_RANDOM in actions


def test_persist_elite():
    engine = DecisionEngine()
    verdict, actions, reason = engine.decide(
        success_rate=0.95,
        normalized_quality=0.95,
        efficiency_score=0.90,
        fitness=0.95,
    )
    assert verdict == DecisionAction.PERSIST
    assert DecisionAction.PERSIST in actions


def test_adjust_params_for_low_quality():
    engine = DecisionEngine()
    verdict, actions, reason = engine.decide(
        success_rate=0.70,
        normalized_quality=0.20,
        efficiency_score=0.80,
        fitness=0.55,
    )
    assert verdict == DecisionAction.ADJUST_PARAMS


def test_adjust_params_for_low_efficiency():
    engine = DecisionEngine()
    verdict, actions, reason = engine.decide(
        success_rate=0.80,
        normalized_quality=0.75,
        efficiency_score=0.30,
        fitness=0.65,
    )
    assert verdict == DecisionAction.ADJUST_PARAMS


def test_mutate_when_fitness_low():
    engine = DecisionEngine()
    verdict, actions, reason = engine.decide(
        success_rate=0.55,
        normalized_quality=0.55,
        efficiency_score=0.60,
        fitness=0.45,
    )
    assert verdict == DecisionAction.MUTATE


def test_retrain_when_fitness_medium():
    engine = DecisionEngine()
    verdict, actions, reason = engine.decide(
        success_rate=0.65,
        normalized_quality=0.60,
        efficiency_score=0.65,
        fitness=0.55,
    )
    assert verdict == DecisionAction.RETRAIN
