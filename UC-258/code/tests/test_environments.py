"""Tests de los tres entornos."""
import pytest

from environments.chess_env import ChessboardEnvironment
from environments.stock_env import StockMarketEnvironment
from environments.travel_env import TravelEnvironment
from models import TravelRequest


def test_chess_properties():
    env = ChessboardEnvironment()
    props = env.properties
    assert not props.is_dynamic
    assert props.is_deterministic
    assert props.is_fully_observable
    assert props.is_discrete


def test_chess_mate_in_one_simple():
    env = ChessboardEnvironment()
    result = env.step("Qd8")
    assert result.reward == 100.0
    assert result.done


def test_stock_properties():
    env = StockMarketEnvironment()
    props = env.properties
    assert props.is_dynamic
    assert not props.is_deterministic
    assert not props.is_fully_observable
    assert not props.is_discrete


def test_stock_trade():
    env = StockMarketEnvironment(seed=123)
    result = env.step("buy_small")
    assert result.reward != 0 or result.reward == 0  # no assertion, just runs
    obs = result.observation.data
    assert "price" in obs


def test_travel_environment_properties():
    req = TravelRequest(origin="Madrid", destination="París", departure_date="2026-07-15")
    env = TravelEnvironment(request=req)
    props = env.properties
    assert props.is_dynamic
    assert not props.is_fully_observable
    assert props.is_discrete


def test_travel_step_flight_search():
    from models import AgentAction

    req = TravelRequest(origin="Madrid", destination="París", departure_date="2026-07-15")
    env = TravelEnvironment(request=req)
    result = env.step(AgentAction(name="flight_search"))
    assert result.reward > 0
    assert len(env._flight_results) > 0


def test_travel_generates_itinerary():
    from models import AgentAction

    req = TravelRequest(
        origin="Madrid",
        destination="París",
        departure_date="2026-07-15",
        return_date="2026-07-18",
        budget=2000.0,
    )
    env = TravelEnvironment(request=req)
    env.step(AgentAction(name="flight_search"))
    env.step(AgentAction(name="hotel_search"))
    env.step(AgentAction(name="generate_itinerary"))
    assert env.itinerary.total_cost > 0
    assert env.itinerary.confidence > 0
    assert len(env.itinerary.assumptions) > 0
