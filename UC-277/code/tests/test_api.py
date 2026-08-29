"""Tests de integracion de la API Flask para UC-277."""
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
    assert resp.get_json()["data"]["service"] == "uc277-multi-turn-memory"


def test_schema(client):
    resp = client.get("/api/v1/schema")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "input_cards" in data
    assert "output_cards" in data
    assert len(data["input_cards"]) >= 6


def test_create_agent(client):
    resp = client.post("/api/v1/agent/create",
                       data=json.dumps({"agent_id": "test_agent"}),
                       content_type="application/json")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["agent_id"] == "test_agent"


def test_create_agent_missing(client):
    resp = client.post("/api/v1/agent/create",
                       data=json.dumps({}),
                       content_type="application/json")
    assert resp.status_code == 400


def test_get_agent(client):
    client.post("/api/v1/agent/create",
                data=json.dumps({"agent_id": "get_agent"}),
                content_type="application/json")
    resp = client.get("/api/v1/agent/get_agent")
    assert resp.status_code == 200


def test_get_agent_not_found(client):
    resp = client.get("/api/v1/agent/no_exist")
    assert resp.status_code == 404


def test_list_agents(client):
    resp = client.get("/api/v1/agents")
    assert resp.status_code == 200


def test_memory_store(client):
    client.post("/api/v1/agent/create",
                data=json.dumps({"agent_id": "store_agent"}),
                content_type="application/json")
    resp = client.post("/api/v1/memory/store",
                       data=json.dumps({
                           "agent_id": "store_agent",
                           "summary": "User asked about BTC price",
                           "episode_type": "interaction",
                           "tags": ["btc", "price"],
                           "importance": "high",
                           "sentiment": 0.5,
                       }),
                       content_type="application/json")
    assert resp.status_code == 200
    assert "episode_id" in resp.get_json()["data"]


def test_memory_store_missing(client):
    resp = client.post("/api/v1/memory/store",
                       data=json.dumps({"agent_id": "x"}),
                       content_type="application/json")
    assert resp.status_code == 400


def test_memory_recall(client):
    client.post("/api/v1/agent/create",
                data=json.dumps({"agent_id": "recall_agent"}),
                content_type="application/json")
    client.post("/api/v1/memory/store",
                data=json.dumps({
                    "agent_id": "recall_agent",
                    "summary": "Machine learning is great for predictions",
                }),
                content_type="application/json")
    resp = client.post("/api/v1/memory/recall",
                       data=json.dumps({
                           "agent_id": "recall_agent",
                           "query": "machine learning",
                       }),
                       content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "episodic" in data
    assert "semantic" in data


def test_memory_recall_missing(client):
    resp = client.post("/api/v1/memory/recall",
                       data=json.dumps({"agent_id": "x"}),
                       content_type="application/json")
    assert resp.status_code == 400


def test_memory_consolidate(client):
    client.post("/api/v1/agent/create",
                data=json.dumps({"agent_id": "consol_agent"}),
                content_type="application/json")
    client.post("/api/v1/memory/store",
                data=json.dumps({
                    "agent_id": "consol_agent",
                    "summary": "Critical event",
                    "importance": "critical",
                }),
                content_type="application/json")
    resp = client.post("/api/v1/memory/consolidate",
                       data=json.dumps({"agent_id": "consol_agent"}),
                       content_type="application/json")
    assert resp.status_code == 200
    assert "consolidated_to_semantic" in resp.get_json()["data"]


def test_new_session(client):
    client.post("/api/v1/agent/create",
                data=json.dumps({"agent_id": "sess_agent"}),
                content_type="application/json")
    resp = client.post("/api/v1/session/new",
                       data=json.dumps({"agent_id": "sess_agent"}),
                       content_type="application/json")
    assert resp.status_code == 200
    assert "session_id" in resp.get_json()["data"]


def test_session_episodes(client):
    resp = client.get("/api/v1/session/nonexistent/episodes")
    assert resp.status_code == 200
    assert resp.get_json()["data"] == []


def test_episodic_search(client):
    client.post("/api/v1/agent/create",
                data=json.dumps({"agent_id": "ep_agent"}),
                content_type="application/json")
    client.post("/api/v1/memory/store",
                data=json.dumps({
                    "agent_id": "ep_agent",
                    "summary": "Bitcoin price analysis",
                    "tags": ["btc"],
                }),
                content_type="application/json")
    resp = client.post("/api/v1/episodic/search",
                       data=json.dumps({
                           "agent_id": "ep_agent",
                           "query": "BTC",
                       }),
                       content_type="application/json")
    assert resp.status_code == 200


def test_episodic_by_tag(client):
    resp = client.get("/api/v1/episodic/by-tag/btc?agent_id=ep_agent")
    assert resp.status_code == 200


def test_semantic_add_fact(client):
    client.post("/api/v1/agent/create",
                data=json.dumps({"agent_id": "sem_agent"}),
                content_type="application/json")
    resp = client.post("/api/v1/semantic/add-fact",
                       data=json.dumps({
                           "agent_id": "sem_agent",
                           "content": "User prefers conservative trades",
                       }),
                       content_type="application/json")
    assert resp.status_code == 200
    assert "node_id" in resp.get_json()["data"]


def test_semantic_query(client):
    client.post("/api/v1/agent/create",
                data=json.dumps({"agent_id": "sq_agent"}),
                content_type="application/json")
    client.post("/api/v1/semantic/add-fact",
                data=json.dumps({"agent_id": "sq_agent", "content": "BTC is digital gold"}),
                content_type="application/json")
    resp = client.post("/api/v1/semantic/query",
                       data=json.dumps({"agent_id": "sq_agent", "query": "bitcoin gold"}),
                       content_type="application/json")
    assert resp.status_code == 200


def test_semantic_preferences(client):
    resp = client.get("/api/v1/semantic/preferences/any_agent")
    assert resp.status_code == 200


def test_create_goal(client):
    client.post("/api/v1/agent/create",
                data=json.dumps({"agent_id": "goal_agent"}),
                content_type="application/json")
    resp = client.post("/api/v1/goals/create",
                       data=json.dumps({
                           "agent_id": "goal_agent",
                           "title": "Reach 10% ROI",
                           "description": "Monthly target",
                           "priority": 0.8,
                       }),
                       content_type="application/json")
    assert resp.status_code == 200
    assert "goal_id" in resp.get_json()["data"]


def test_create_goal_missing(client):
    resp = client.post("/api/v1/goals/create",
                       data=json.dumps({"agent_id": "x"}),
                       content_type="application/json")
    assert resp.status_code == 400


def test_list_goals(client):
    resp = client.get("/api/v1/goals/goal_agent")
    assert resp.status_code == 200


def test_update_goal_progress(client):
    client.post("/api/v1/agent/create",
                data=json.dumps({"agent_id": "prog_agent"}),
                content_type="application/json")
    r = client.post("/api/v1/goals/create",
                    data=json.dumps({
                        "agent_id": "prog_agent",
                        "title": "Test Goal",
                    }),
                    content_type="application/json")
    goal_id = r.get_json()["data"]["goal_id"]
    resp = client.post("/api/v1/goals/update-progress",
                       data=json.dumps({"goal_id": goal_id, "progress": 0.5}),
                       content_type="application/json")
    assert resp.status_code == 200


def test_system_status(client):
    resp = client.get("/api/v1/system/status")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["service"] == "uc277-multi-turn-memory"
    assert "total_agents" in data
    assert "total_episodes" in data
