"""Tests de integración de la API Flask."""
from __future__ import annotations

import json

import pytest

from api import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200


def test_schema(client) -> None:
    resp = client.get("/api/v1/schema")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "input_cards" in data
    assert "output_cards" in data


def test_plan_endpoint(client) -> None:
    payload = {
        "origin": "Madrid",
        "destination": "Barcelona",
        "departure_date": "2026-09-15",
        "return_date": "2026-09-17",
        "travelers": 1,
        "budget": 2000,
        "confirm_irreversible": True,
        "user_id": "api-generic-user",
        "preferences": {"airline": "Delta"},
        "long_term_goals": ["Mantener estatus Platino"],
    }
    resp = client.post(
        "/api/v1/generic/plan",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["status"] in ("done", "awaiting_confirmation", "awaiting_collaboration")
    assert data["total_cost"] > 0
    assert data["best_candidate"]


def test_memory_endpoint(client) -> None:
    resp = client.get("/api/v1/memory/api-generic-user")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["user_id"] == "api-generic-user"
