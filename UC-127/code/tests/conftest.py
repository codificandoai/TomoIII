"""Fixtures compartidos para las pruebas de UC-127."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("UC127_INTEGRATIONS_DRY_RUN", "true")

import pytest

from orchestrator import IncidentResponseOrchestrator
from playbooks.loader import PlaybookLoader


@pytest.fixture()
def playbook_loader() -> PlaybookLoader:
    return PlaybookLoader()


@pytest.fixture()
def orchestrator(playbook_loader) -> IncidentResponseOrchestrator:
    return IncidentResponseOrchestrator(playbook_loader=playbook_loader)
