"""
Fixtures compartidas para tests de UC-308.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "UC-317", "code")))

from drift_orchestrator import DriftOrchestrator
from environment_simulator import SimulatedExternalEnvironment
from golden_dataset import build_default_golden_dataset
from models_308 import DriftConfig


@pytest.fixture
def config() -> DriftConfig:
    return DriftConfig()


@pytest.fixture
def dataset():
    return build_default_golden_dataset(version="test-1.0.0")


@pytest.fixture
def environment() -> SimulatedExternalEnvironment:
    return SimulatedExternalEnvironment(seed=12345)


@pytest.fixture
def orchestrator(dataset, environment, config) -> DriftOrchestrator:
    """Orquestador con baselines iniciales listas para tests."""
    orch = DriftOrchestrator(
        config=config,
        dataset=dataset,
        environment=environment,
    )
    orch.initialize_baselines(scenario="healthy")
    return orch


@pytest.fixture
def api_client():
    """Cliente Flask de prueba para api_308."""
    from api_308 import app
    app.config["TESTING"] = True
    return app.test_client()
