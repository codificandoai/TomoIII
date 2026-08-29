import pytest

import api
from orchestrator import GoalOrchestrator
from store import GoalStore


@pytest.fixture
def client():
    api.orchestrator = GoalOrchestrator(GoalStore())
    api.app.config["TESTING"] = True
    return api.app.test_client()


def test_health_and_schema(client):
    assert client.get("/health").status_code == 200
    schema = client.get("/api/v1/schema").get_json()["data"]
    assert len(schema["input_cards"]) == 2
    assert len(schema["output_cards"]) == 2


@pytest.mark.parametrize("planner", ["langgraph", "tdag", "reactree"])
def test_create_and_execute_goal(client, planner):
    response = client.post("/api/v1/goals", json={"description": "Build a production API", "planner": planner,
                                                   "context": {"owner": "platform"}})
    assert response.status_code == 201
    data = response.get_json()["data"]
    goal_id = data["goal"]["id"]
    assert data["goal"]["planner"] == planner
    executed = client.post(f"/api/v1/goals/{goal_id}/execute")
    result = executed.get_json()["data"]
    assert executed.status_code == 200
    assert result["status"] == "completed"
    assert len(result["audit_hash"]) == 64
    assert client.get(f"/api/v1/goals/{goal_id}/events").status_code == 200


def test_list_and_get(client):
    created = client.post("/api/v1/goals", json={"description": "Analyze evidence"}).get_json()["data"]
    goal_id = created["goal"]["id"]
    assert len(client.get("/api/v1/goals").get_json()["data"]) == 1
    assert client.get(f"/api/v1/goals/{goal_id}").status_code == 200


def test_api_validation(client):
    assert client.post("/api/v1/goals", json={}).status_code == 400
    assert client.post("/api/v1/goals", json={"description": "x", "planner": "invalid"}).status_code == 400
    assert client.get("/api/v1/goals/missing").status_code == 404
