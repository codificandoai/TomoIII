"""Tests del cliente del predictor de retrasos."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from external_api import FlightDelayPredictor


def test_flight_to_prediction_request() -> None:
    from external_api import flight_to_prediction_request

    item = {
        "item_type": "flight",
        "id": "FL-MADBAR-103",
        "details": {
            "airline": "AA",
            "origin": "Madrid",
            "destination": "Barcelona",
            "departure": "2026-09-15T08:00:00",
            "arrival": "2026-09-15T10:00:00",
            "flight_number": "AA103",
            "cabin_class": "Y",
            "aircraft_type": "B738",
        },
    }
    req = flight_to_prediction_request(item)
    assert req is not None
    assert req["OPERA"] == "AA"
    assert req["SIGLAORI"] == "Madrid"
    assert req["SIGLAPOS"] == "Barcelona"
    assert req["MES"] == 9
    assert req["DIA"] == 15


def test_predictor_success(monkeypatch) -> None:
    predictor = FlightDelayPredictor()

    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"delay_probability": 0.85, "predicted_delay_minutes": 120, "confidence": 0.9}
    ]
    mock_response.raise_for_status.return_value = None

    def mock_post(*args, **kwargs):
        return mock_response

    monkeypatch.setattr("requests.post", mock_post)

    items = [
        {
            "item_type": "flight",
            "id": "FL-1",
            "details": {
                "airline": "AA",
                "origin": "MAD",
                "destination": "BCN",
                "departure": "2026-09-15T08:00:00",
                "arrival": "2026-09-15T10:00:00",
                "flight_number": "AA101",
                "cabin_class": "Y",
                "aircraft_type": "B738",
            },
        }
    ]
    result = predictor.predict(items)
    assert result["success"] is True
    assert result["source"] == "flight_delays_api"
    assert len(result["predictions"]) == 1
    assert result["predictions"][0]["delay_probability"] == 0.85


def test_predictor_timeout_falls_back(monkeypatch) -> None:
    predictor = FlightDelayPredictor()

    def mock_post(*args, **kwargs):
        raise Exception("timeout")

    monkeypatch.setattr("requests.post", mock_post)

    items = [
        {
            "item_type": "flight",
            "id": "FL-1",
            "details": {
                "airline": "AA",
                "origin": "MAD",
                "destination": "BCN",
                "departure": "2026-09-15T08:00:00",
                "arrival": "2026-09-15T10:00:00",
                "flight_number": "AA101",
                "cabin_class": "Y",
                "aircraft_type": "B738",
            },
        }
    ]
    result = predictor.predict(items)
    assert result["success"] is False
    assert result["source"] == "fallback"
    assert len(result["predictions"]) == 1
    assert result["predictions"][0]["delay_probability"] == 0.0
