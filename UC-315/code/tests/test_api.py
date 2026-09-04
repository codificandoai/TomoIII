"""Tests de la API REST Flask UC-315."""
from __future__ import annotations

import pytest

from api import app


@pytest.fixture
def client():
    app.testing = True
    return app.test_client()


def test_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "input_cards" in data["data"]


def test_list_skills(client):
    resp = client.get("/api/v1/skills?domain=reservations")
    assert resp.status_code == 200
    skills = resp.get_json()["data"]
    assert any(s["name"] == "FlightBookingSkill" for s in skills)


def test_build_plan(client):
    resp = client.post("/api/v1/plan", json={
        "goal": "Reservar un tren de Madrid a Barcelona",
        "domain": "reservations",
    })
    assert resp.status_code == 200
    plan = resp.get_json()["data"]
    assert plan["domain"] == "reservations"
    assert any(s["skill_name"] == "RailBookingSkill" for s in plan["steps"])


def test_orchestrate_auto_approve(client):
    resp = client.post("/api/v1/orchestrate", json={
        "goal": "Enviar orden de compra AAPL",
        "domain": "trading",
        "user_roles": ["trader", "market.order.send"],
        "domain_state": {"risk_approved": True, "circuit_breaker_open": True},
        "auto_approve": True,
    })
    assert resp.status_code == 200
    plan = resp.get_json()["data"]
    assert plan["status"] == "completed"


def test_safety_check(client):
    resp = client.post("/api/v1/safety/check", json={
        "skill_name": "MarketExecutionSkill",
        "user_roles": ["analyst"],
        "domain_state": {"risk_approved": True, "circuit_breaker_open": True},
    })
    assert resp.status_code == 200
    decision = resp.get_json()["data"]
    assert not decision["allowed"]
