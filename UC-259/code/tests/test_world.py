"""Tests del simulador del mundo externo."""
from __future__ import annotations

import pytest

from config import get_config
from world_simulator import WorldSimulator


@pytest.fixture
def world() -> WorldSimulator:
    return WorldSimulator(get_config().world)


def test_search_flights_returns_multiple(world: WorldSimulator) -> None:
    flights = world.search_flights("Madrid", "Barcelona", "2026-09-15")
    assert len(flights) >= 3
    assert all("flight_id" in f and "departure" in f and "arrival" in f for f in flights)


def test_search_flights_same_city_empty(world: WorldSimulator) -> None:
    assert world.search_flights("Madrid", "Madrid", "2026-09-15") == []


def test_search_hotels(world: WorldSimulator) -> None:
    hotels = world.search_hotels("Barcelona", "2026-09-15", "2026-09-17")
    assert len(hotels) >= 1
    assert "hotel_id" in hotels[0]


def test_book_flight(world: WorldSimulator) -> None:
    flights = world.search_flights("Madrid", "Barcelona", "2026-09-15")
    result = world.book_flight(flights[0]["flight_id"])
    assert result["status"] == "BOOKED"
    assert "confirmation" in result


def test_check_status_event(world: WorldSimulator) -> None:
    world.inject_event("FL-TEST-001", "DELAYED", delay_minutes=180, reason="Maintenance")
    status = world.check_status("FL-TEST-001")
    assert status["status"] == "DELAYED"
    assert status["delay_minutes"] == 180


def test_rebook_flight(world: WorldSimulator) -> None:
    flights = world.search_flights("Madrid", "Barcelona", "2026-09-15")
    original = flights[0]
    result = world.rebook_flight(
        original["flight_id"],
        "Madrid",
        "Barcelona",
        "2026-09-15",
        after=original["arrival"],
    )
    assert result["status"] == "REBOOKED"
    assert "flight" in result
    assert result["flight"]["flight_id"] != original["flight_id"]
