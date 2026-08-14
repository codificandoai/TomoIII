"""Fixtures compartidos para las pruebas de UC-119."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from monitoring_system import LLMMonitoringSystem


@pytest.fixture()
def monitoring_system() -> LLMMonitoringSystem:
    return LLMMonitoringSystem(model_name="test-model", provider="test-provider", model_version="0.0.1")
