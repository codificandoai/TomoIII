"""Configuración compartida para los tests de UC-262."""
import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("UC262_SIMULATED_LATENCY_MS", "0")
os.environ.setdefault("UC262_WORLD_SEED", "123")
os.environ.setdefault("UC262_POPULATION_SIZE", "8")
os.environ.setdefault("UC262_GENERATIONS", "3")
os.environ.setdefault("UC262_MUTATION_RATE", "0.2")
os.environ.setdefault("UC262_ELITE_RATIO", "0.25")
os.environ.setdefault("UC262_CULL_RATIO", "0.3")
os.environ.setdefault("UC262_REQUIRE_CONFIRMATION_IRREVERSIBLE", "true")
os.environ.setdefault("UC262_ENABLE_PROMPT_INJECTION_CHECK", "true")
os.environ.setdefault("UC262_ENABLE_PII_REDACTION", "true")
os.environ.setdefault("UC262_ENABLE_LEARNING", "true")


@pytest.fixture(autouse=True)
def mock_predictor_api(monkeypatch):
    """Evita llamadas HTTP reales en todos los tests."""
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"delay_probability": 0.05, "predicted_delay_minutes": 0, "confidence": 0.9}
    ]
    mock_response.raise_for_status.return_value = None
    monkeypatch.setattr("requests.post", lambda *args, **kwargs: mock_response)
