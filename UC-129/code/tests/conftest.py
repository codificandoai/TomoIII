"""Fixtures compartidos para las pruebas de UC-129."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from incident_service import IncidentMetricsService


@pytest.fixture()
def service() -> IncidentMetricsService:
    return IncidentMetricsService()
