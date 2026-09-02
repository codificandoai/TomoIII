"""Tests del entrenamiento del world model."""
from __future__ import annotations

import tempfile

from train import train_world_model


def test_train_world_model():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = train_world_model(n_samples=50, output_dir=tmpdir)
        assert result["status"] == "trained"
        assert result["metadata"]["n_samples"] == 50
