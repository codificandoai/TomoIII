"""Tests de entrenamiento con datos sintéticos e inferencia con modelo guardado."""
from __future__ import annotations

import os
import shutil
import tempfile

from config import get_config
from model_persistence import ModelPersistence
from synthetic_data import SyntheticDataGenerator
from train import load_trained_model, train_world_model
from travel_world import TravelWorldSimulator
from world_model import TravelWorldModel


def test_generate_synthetic_data() -> None:
    gen = SyntheticDataGenerator(get_config())
    transitions, observations = gen.generate_batch(n=20)
    assert len(transitions) > 0
    assert len(observations) > 0
    assert all("action_type" in o for o in observations)


def test_train_and_save_model() -> None:
    tmpdir = tempfile.mkdtemp()
    try:
        result = train_world_model(n_samples=50, config=get_config(), output_dir=tmpdir)
        assert result["status"] == "trained"
        assert result["metadata"]["n_samples"] == 50
        assert result["metadata"]["n_transitions"] > 0
        assert result["metadata"]["model_type"] == "neural"
        assert os.path.exists(os.path.join(tmpdir, "model_metadata.json"))
        assert os.path.exists(os.path.join(tmpdir, "neural_success_model.joblib"))
        assert os.path.exists(os.path.join(tmpdir, "neural_reward_model.joblib"))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_load_and_infer_trained_model() -> None:
    tmpdir = tempfile.mkdtemp()
    try:
        train_world_model(n_samples=50, config=get_config(), output_dir=tmpdir)
        cfg = get_config()
        simulator = TravelWorldSimulator(cfg.world)
        world_model = TravelWorldModel(cfg.model, simulator, app_config=cfg)
        attached = load_trained_model(world_model, output_dir=tmpdir)
        assert attached is True
        from models import PlanAction, WorldModelState

        state = WorldModelState(remaining_budget=2000, preferences={"airline": "Delta"})
        action = PlanAction(action_type="flight", item_id="FL-INF", estimated_cost=300)
        success, reward, uncertainty = world_model._predict_success_and_reward(state, action)
        assert 0.0 <= success <= 1.0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
