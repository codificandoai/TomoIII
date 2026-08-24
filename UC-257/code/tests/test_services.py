"""Tests de los servicios de viaje simulados."""
import pytest

from models import Activity, Flight, Hotel, Meeting, ServiceType
from travel_services import BookingManager, TravelInventory


def test_search_flights_returns_sorted_by_price():
    inv = TravelInventory()
    flights = inv.search_flights("Madrid", "París", "2026-07-15")
    assert len(flights) == 3
    assert flights[0].price <= flights[1].price <= flights[2].price


def test_book_and_cancel_flight():
    inv = TravelInventory()
    bm = BookingManager(inv)
    flights = inv.search_flights("Madrid", "París", "2026-07-15")
    booking = bm.create_booking(ServiceType.FLIGHT, flights[0].flight_id, flights[0].to_dict())
    assert booking.service_type == ServiceType.FLIGHT
    inv.cancel_flight(flights[0].flight_id)
    assert inv.get_flight(flights[0].flight_id).status == "cancelled"


def test_rebook_flight_excludes_cancelled_one():
    inv = TravelInventory()
    bm = BookingManager(inv)
    flights = inv.search_flights("Madrid", "París", "2026-07-15")
    inv.cancel_flight(flights[0].flight_id)
    new = bm.rebook_flight(flights[0].flight_id, "Madrid", "París", "2026-07-15")
    assert new is not None
    assert new.flight_id != flights[0].flight_id


def test_search_hotels_and_activities():
    inv = TravelInventory()
    hotels = inv.search_hotels("París", "2026-07-15", "2026-07-18")
    assert len(hotels) >= 1
    activities = inv.search_activities("París", "2026-07-15")
    assert len(activities) >= 1


def test_reschedule_meeting():
    inv = TravelInventory()
    assert inv.reschedule_meeting("meet-15", "2026-07-15T17:00:00", "retraso vuelo")
    meeting = inv.get_meeting("meet-15")
    assert meeting.status == "rescheduled"
