"""Tests de integración de la API Flask para UC-276."""
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
    data = resp.get_json()["data"]
    assert data["service"] == "uc276-recursive-prompting"


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
                data=json.dumps({"agent_id": "get_test"}),
                content_type="application/json")
    resp = client.get("/api/v1/agent/get_test")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["agent_id"] == "get_test"


def test_get_agent_not_found(client):
    resp = client.get("/api/v1/agent/nonexistent")
    assert resp.status_code == 404


def test_list_agents(client):
    client.post("/api/v1/agent/create",
                data=json.dumps({"agent_id": "list_a1"}),
                content_type="application/json")
    resp = client.get("/api/v1/agents")
    assert resp.status_code == 200
    assert isinstance(resp.get_json()["data"], list)


def test_recursive_run(client):
    client.post("/api/v1/agent/create",
                data=json.dumps({"agent_id": "run_agent"}),
                content_type="application/json")
    resp = client.post("/api/v1/recursive/run",
                       data=json.dumps({
                           "agent_id": "run_agent",
                           "input_data": "Machine learning is AI that learns from data patterns.",
                           "task_description": "Summarize clearly and concisely",
                           "context": {"audience": "executives"},
                       }),
                       content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "session_id" in data
    assert "final_score" in data
    assert "improvement_trajectory" in data
    assert "session_hash" in data


def test_recursive_run_missing_params(client):
    resp = client.post("/api/v1/recursive/run",
                       data=json.dumps({"agent_id": "x"}),
                       content_type="application/json")
    assert resp.status_code == 400


def test_recursive_refine(client):
    resp = client.post("/api/v1/recursive/refine",
                       data=json.dumps({
                           "content": "This is a text that needs to be made more clear and concise.",
                           "strategy": "clarify",
                           "task_description": "Improve clarity",
                       }),
                       content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "original_score" in data
    assert "refined_score" in data
    assert "improvement" in data
    assert "refined_content" in data


def test_recursive_refine_invalid_strategy(client):
    resp = client.post("/api/v1/recursive/refine",
                       data=json.dumps({
                           "content": "test",
                           "strategy": "invalid_strategy",
                       }),
                       content_type="application/json")
    assert resp.status_code == 400


def test_recursive_evaluate(client):
    resp = client.post("/api/v1/recursive/evaluate",
                       data=json.dumps({
                           "content": "Machine learning uses algorithms to identify patterns in data.",
                           "original_input": "A long text about machine learning algorithms and data patterns...",
                           "task_description": "Summarize",
                       }),
                       content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "overall_score" in data
    assert "quality_level" in data
    assert "criteria_scores" in data
    assert "issues" in data
    assert "strengths" in data


def test_recursive_evaluate_empty(client):
    resp = client.post("/api/v1/recursive/evaluate",
                       data=json.dumps({}),
                       content_type="application/json")
    assert resp.status_code == 400


def test_recursive_rsi(client):
    resp = client.post("/api/v1/recursive/rsi",
                       data=json.dumps({
                           "agent_id": "rsi_test",
                           "task": "Improve this algorithm",
                           "current_output": "A basic sorting algorithm that iterates through the list.",
                           "max_cycles": 3,
                       }),
                       content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "baseline_score" in data
    assert "final_score" in data
    assert "total_improvement" in data
    assert "cycles_run" in data


def test_recursive_rsi_missing_task(client):
    resp = client.post("/api/v1/recursive/rsi",
                       data=json.dumps({"current_output": "something"}),
                       content_type="application/json")
    assert resp.status_code == 400


def test_list_sessions(client):
    resp = client.get("/api/v1/recursive/sessions")
    assert resp.status_code == 200
    assert isinstance(resp.get_json()["data"], list)


def test_get_session_not_found(client):
    resp = client.get("/api/v1/recursive/session/nonexistent")
    assert resp.status_code == 404


def test_list_strategies(client):
    resp = client.get("/api/v1/recursive/strategies")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 8
    assert all("name" in s and "prompt_template" in s for s in data)


def test_check_stagnation(client):
    resp = client.post("/api/v1/recursive/stagnation/check",
                       data=json.dumps({"trajectory": [0.5, 0.51, 0.515, 0.516]}),
                       content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "is_stagnated" in data
    assert "reason" in data


def test_check_stagnation_short_trajectory(client):
    resp = client.post("/api/v1/recursive/stagnation/check",
                       data=json.dumps({"trajectory": [0.5]}),
                       content_type="application/json")
    assert resp.status_code == 400


def test_stats(client):
    resp = client.get("/api/v1/stats")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "total_agents" in data
    assert "total_sessions" in data


def test_system_status(client):
    resp = client.get("/api/v1/system/status")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["service"] == "uc276-recursive-prompting"
    assert "total_agents" in data
    assert "config" in data


def test_recursive_run_creates_session(client):
    """Integration: run and then fetch session."""
    client.post("/api/v1/agent/create",
                data=json.dumps({"agent_id": "integ_agent"}),
                content_type="application/json")
    resp = client.post("/api/v1/recursive/run",
                       data=json.dumps({
                           "agent_id": "integ_agent",
                           "input_data": "Content to process for integration test.",
                           "task_description": "Generate summary",
                       }),
                       content_type="application/json")
    assert resp.status_code == 200
    session_id = resp.get_json()["data"]["session_id"]

    sess_resp = client.get(f"/api/v1/recursive/session/{session_id}")
    assert sess_resp.status_code == 200
    assert sess_resp.get_json()["data"]["session_id"] == session_id
    assert "versions" in sess_resp.get_json()["data"]
