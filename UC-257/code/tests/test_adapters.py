"""Tests de los adaptadores Semantic Kernel y AutoGen."""
import pytest

from agent_orchestrator import TravelAgentOrchestrator
from autogen_adapter import AutoGenAdapter
from config import AppConfig
from models import TripRequest
from semantic_kernel_adapter import SemanticKernelAdapter
from travel_services import BookingManager, TravelInventory


@pytest.fixture
def adapters():
    config = AppConfig()
    config.frameworks.use_semantic_kernel = False
    config.frameworks.use_autogen = False
    config.llm.provider = "stub"
    inventory = TravelInventory()
    bookings = BookingManager(inventory)
    orchestrator = TravelAgentOrchestrator(inventory, bookings)
    sk = SemanticKernelAdapter(config, orchestrator)
    autogen = AutoGenAdapter(config, orchestrator)
    return sk, autogen


def test_semantic_kernel_fallback_deterministic(adapters):
    sk, _ = adapters
    result = sk.chat("u1", "Busca vuelos de Madrid a París")
    assert result["mode"] == "assistant"
    assert result["action"]["success"] is True


def test_autogen_adapter_runs_autonomous(adapters):
    _, autogen = adapters
    request = TripRequest(
        origin="Madrid",
        destination="París",
        departure_date="2026-07-15",
        return_date="2026-07-18",
        meeting_ids=["meet-15"],
    )
    result = autogen.run(request)
    assert result.status == "completed"
    assert result.final_state["selected_flight"] is not None
