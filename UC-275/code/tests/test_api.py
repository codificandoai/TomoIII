"""Tests de integración de la API Flask para UC-275."""
from __future__ import annotations

import json

import pytest

from api import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["service"] == "uc275-agent-self-reflection"


def test_schema(client):
    resp = client.get("/api/v1/schema")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "input_cards" in data
    assert "output_cards" in data
    assert len(data["input_cards"]) >= 6
    assert len(data["output_cards"]) >= 5


def test_create_agent(client):
    resp = client.post("/api/v1/agent/create",
                       data=json.dumps({"agent_id": "test_agent_1"}),
                       content_type="application/json")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["agent_id"] == "test_agent_1"


def test_create_agent_missing_id(client):
    resp = client.post("/api/v1/agent/create",
                       data=json.dumps({}),
                       content_type="application/json")
    assert resp.status_code == 400


def test_get_agent(client):
    client.post("/api/v1/agent/create",
                data=json.dumps({"agent_id": "get_agent_1"}),
                content_type="application/json")
    resp = client.get("/api/v1/agent/get_agent_1")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["agent_id"] == "get_agent_1"


def test_list_agents(client):
    client.post("/api/v1/agent/create",
                data=json.dumps({"agent_id": "list_a1"}),
                content_type="application/json")
    resp = client.get("/api/v1/agents")
    assert resp.status_code == 200
    assert isinstance(resp.get_json()["data"], list)


def test_reflect_run(client):
    client.post("/api/v1/agent/create",
                data=json.dumps({"agent_id": "reflect_agent"}),
                content_type="application/json")
    resp = client.post("/api/v1/reflect/run",
                       data=json.dumps({
                           "agent_id": "reflect_agent",
                           "action_params": {"type": "trade", "risk_tolerance": 0.5},
                           "expected_outcome": {"correctness": 0.8, "completeness": 0.7},
                           "context": {"market": "crypto"},
                       }),
                       content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "episode_id" in data
    assert "final_score" in data
    assert "reflection_hash" in data


def test_reflect_run_missing_params(client):
    resp = client.post("/api/v1/reflect/run",
                       data=json.dumps({"agent_id": "x"}),
                       content_type="application/json")
    assert resp.status_code == 400


def test_self_refine(client):
    resp = client.post("/api/v1/reflect/self-refine",
                       data=json.dumps({
                           "agent_id": "sr_agent",
                           "task": "Implementa una funcion que duplique un numero",
                       }),
                       content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "output" in data
    assert "score" in data
    assert "iterations" in data


def test_self_refine_missing_task(client):
    resp = client.post("/api/v1/reflect/self-refine",
                       data=json.dumps({}),
                       content_type="application/json")
    assert resp.status_code == 400


def test_evaluate_metrics(client):
    resp = client.post("/api/v1/reflect/evaluate",
                       data=json.dumps({
                           "actual_metrics": {"correctness": 0.9, "completeness": 0.6},
                           "expected_metrics": {"correctness": 0.8, "completeness": 0.8},
                       }),
                       content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "outcome" in data
    assert "score" in data
    assert "needs_reflection" in data


def test_evaluate_missing_metrics(client):
    resp = client.post("/api/v1/reflect/evaluate",
                       data=json.dumps({}),
                       content_type="application/json")
    assert resp.status_code == 400


def test_critique(client):
    resp = client.post("/api/v1/reflect/critique",
                       data=json.dumps({
                           "actual_metrics": {"correctness": 0.3, "prediction_error": 0.5},
                           "expected_metrics": {"correctness": 0.8, "prediction_error": 0.1},
                       }),
                       content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "evaluation" in data
    assert "root_cause" in data
    assert "category" in data["root_cause"]


def test_list_episodes(client):
    resp = client.get("/api/v1/reflect/episodes")
    assert resp.status_code == 200
    assert isinstance(resp.get_json()["data"], list)


def test_get_episode_not_found(client):
    resp = client.get("/api/v1/reflect/episode/nonexistent")
    assert resp.status_code == 404


def test_memory_lessons(client):
    resp = client.get("/api/v1/memory/lessons/trade")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "success_rate" in data


def test_memory_similar(client):
    resp = client.post("/api/v1/memory/similar",
                       data=json.dumps({
                           "action_type": "trade",
                           "action_params": {"risk": 0.5},
                       }),
                       content_type="application/json")
    assert resp.status_code == 200


def test_memory_stats(client):
    resp = client.get("/api/v1/memory/stats")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "total_episodes" in data


def test_system_status(client):
    resp = client.get("/api/v1/system/status")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "total_episodes" in data
    assert "registered_agents" in data


def test_reflect_run_creates_episode(client):
    """Integration: run reflection and then fetch the episode."""
    resp = client.post("/api/v1/reflect/run",
                       data=json.dumps({
                           "agent_id": "integ_agent",
                           "action_params": {"type": "trade"},
                           "expected_outcome": {"correctness": 0.7},
                       }),
                       content_type="application/json")
    assert resp.status_code == 200
    episode_id = resp.get_json()["data"]["episode_id"]

    ep_resp = client.get(f"/api/v1/reflect/episode/{episode_id}")
    assert ep_resp.status_code == 200
    assert ep_resp.get_json()["data"]["episode_id"] == episode_id
