"""Fixtures compartidas para tests UC-257."""
import pytest

from agent_orchestrator import TravelAgentOrchestrator
from travel_services import BookingManager, TravelInventory


@pytest.fixture
def inventory():
    return TravelInventory()


@pytest.fixture
def booking_manager(inventory):
    return BookingManager(inventory)


@pytest.fixture
def orchestrator(inventory, booking_manager):
    return TravelAgentOrchestrator(inventory, booking_manager)
