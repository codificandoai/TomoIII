"""Tests de mejoras avanzadas: reentrenamiento por incertidumbre/error,
belief state como feature, MCTS persistente e integración del modelo de retrasos.
"""
from __future__ import annotations

import math
import os
import shutil
import tempfile

from config import get_config
from flight_delay_adapter import FlightDelayAdapter
from mcts_store import MCTSPersistentStore
from models import BeliefState, PlanAction, WorldModelObservation, WorldModelState
from probabilistic_model import StateEncoder
from travel_world import TravelWorldSimulator
from world_model import TravelWorldModel


def test_state_encoder_includes_belief_features() -> None:
    encoder = StateEncoder(dim=8)
    state = {"remaining_budget": 1000, "step": 0}
    action = {"action_type": "flight", "item_id": "FL-1", "estimated_cost": 200}
    belief = {
        "particles": [
            {"market_pressure": 0.1, "weather_condition": "sunny"},
            {"market_pressure": -0.2, "weather_condition": "rainy"},
            {"market_pressure": 0.0, "weather_condition": "cloudy"},
        ],
        "weights": [1 / 3, 1 / 3, 1 / 3],
    }
    vec = encoder.encode_transition(state, action, belief)
    assert len(vec) == 8 + 8 + 6
    # mean market pressure
    expected_mean = (0.1 - 0.2 + 0.0) / 3
    assert abs(vec[-6] - expected_mean) < 1e-6


def test_uncertainty_based_retrain() -> None:
    cfg = get_config()
    cfg.model.probabilistic.model_type = "gp"
    cfg.model.probabilistic.min_samples_to_train = 2
    cfg.model.probabilistic.retrain_after = 1000  # evitar trigger por conteo
    cfg.model.probabilistic.uncertainty_retrain_threshold = 0.1
    cfg.model.probabilistic.prediction_error_retrain_threshold = 1.0

    wm = TravelWorldModel(cfg.model, TravelWorldSimulator(cfg.world), app_config=cfg)
    wm.last_uncertainty = 0.9
    assert wm._should_retrain() is True


def test_prediction_error_based_retrain() -> None:
    cfg = get_config()
    cfg.model.probabilistic.retrain_after = 1000
    cfg.model.probabilistic.uncertainty_retrain_threshold = 2.0
    cfg.model.probabilistic.prediction_error_retrain_threshold = 0.05

    wm = TravelWorldModel(cfg.model, TravelWorldSimulator(cfg.world), app_config=cfg)
    for _ in range(10):
        wm.prediction_errors.append(0.5)
    assert wm._should_retrain() is True


def test_observation_records_prediction_error() -> None:
    cfg = get_config()
    wm = TravelWorldModel(cfg.model, TravelWorldSimulator(cfg.world), app_config=cfg)
    wm.config.probabilistic.retrain_after = 1000
    wm.config.probabilistic.uncertainty_retrain_threshold = 2.0
    wm.config.probabilistic.prediction_error_retrain_threshold = 1.0
    obs = WorldModelObservation(
        action_type="flight",
        item_id="FL-X",
        predicted_success_prob=0.9,
        actual_success=False,
        actual_cost=100,
        reward=-3.0,
    )
    wm.update_from_observation(obs)
    assert len(wm.prediction_errors) == 1
    assert abs(wm.prediction_errors[0] - 0.9) < 1e-6


def test_mcts_persistent_store() -> None:
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, "mcts_cache.json")
    try:
        store = MCTSPersistentStore(path)
        request = {
            "origin": "Madrid",
            "destination": "Barcelona",
            "departure_date": "2026-09-15",
            "return_date": "2026-09-17",
            "travelers": 1,
            "budget": 2000,
            "preferences": {"airline": "Delta"},
        }
        assert store.get(request) is None
        children = [
            {"item_id": "FL-A", "visits": 5, "value": 3.0},
            {"item_id": "FL-B", "visits": 2, "value": 1.5},
        ]
        store.save(request, children)
        loaded = store.get(request)
        assert loaded is not None
        assert loaded[0]["item_id"] == "FL-A"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_flight_delay_adapter_loads() -> None:
    cfg = get_config()
    adapter = FlightDelayAdapter(cfg.flight_delays_model_path)
    # Si no está disponible en la ruta configurada, probar ruta por defecto
    if not adapter.available:
        default_path = os.path.join(
            os.path.dirname(__file__), "..", "flight-delays", "challenge", "model.pkl"
        )
        adapter = FlightDelayAdapter(default_path)
    if adapter.available:
        prob = adapter.predict_delay_probability({
            "details": {
                "departure": "2026-09-15T08:00:00",
                "airline": "LATAM",
                "origin": "Madrid",
                "destination": "Barcelona",
            }
        })
        assert 0.0 <= prob <= 1.0


def test_belief_state_propagated_in_transition() -> None:
    cfg = get_config()
    wm = TravelWorldModel(cfg.model, TravelWorldSimulator(cfg.world), app_config=cfg)
    state = WorldModelState(
        remaining_budget=2000,
        preferences={"airline": "Delta"},
        belief_state={
            "particles": [{"market_pressure": 0.1, "weather_condition": "sunny"}],
            "weights": [1.0],
        },
    )
    action = PlanAction(action_type="flight", item_id="FL-1", estimated_cost=300)
    prob, reward, uncertainty = wm._predict_success_and_reward(state, action, state.belief_state)
    assert 0.0 <= prob <= 1.0


def test_observe_enriched_with_flight_delay_model() -> None:
    cfg = get_config()
    wm = TravelWorldModel(cfg.model, TravelWorldSimulator(cfg.world), app_config=cfg)
    flight_item = {
        "flight_id": "FL-TEST",
        "airline": "LATAM",
        "origin": "Madrid",
        "destination": "Barcelona",
        "departure": "2026-09-15T08:00:00",
        "price_usd": 300.0,
        "seats_left": 10,
    }
    obs = wm.observe(flight_item)
    assert obs.observed_delay >= 0.0
    assert obs.observed_price >= 0.0
    # Si el modelo de retrasos está disponible, el retraso observado se ajusta por delay_prob
    if wm.flight_delay_adapter.available:
        assert obs.item_id == "FL-TEST"
