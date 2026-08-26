"""Configuración compartida para los tests de UC-261."""
import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("UC261_SIMULATED_LATENCY_MS", "0")
os.environ.setdefault("UC261_WORLD_SEED", "123")
os.environ.setdefault("UC261_REQUIRE_CONFIRMATION_IRREVERSIBLE", "true")
os.environ.setdefault("UC261_ENABLE_PROMPT_INJECTION_CHECK", "true")
os.environ.setdefault("UC261_ENABLE_PII_REDACTION", "true")
os.environ.setdefault("UC261_ENABLE_LEARNING", "true")
os.environ.setdefault("UC261_PATTERN_MATCH_THRESHOLD", "0.6")
os.environ.setdefault("UC261_AUTO_COST_THRESHOLD", "200.0")


@pytest.fixture(autouse=True)
def mock_predictor_api(monkeypatch):
    """Evita llamadas HTTP reales en todos los tests."""
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"delay_probability": 0.05, "predicted_delay_minutes": 0, "confidence": 0.9}
    ]
    mock_response.raise_for_status.return_value = None
    monkeypatch.setattr("requests.post", lambda *args, **kwargs: mock_response)
