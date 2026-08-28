"""Tests de integración de la API Flask A2A."""
from __future__ import annotations

import pytest

from a2a_server import app
from security import SecurityManager


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def token(client):
    mgr = SecurityManager()
    return mgr.generate_token("test-user", ["a2a:read", "a2a:write"])


def test_health(client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["service"] == "uc268-a2a-secure-agent"


def test_agent_card(client) -> None:
    resp = client.get("/.well-known/agent.json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["name"]
    assert "capabilities" in data
    assert "security_schemes" in data


def test_schema(client) -> None:
    resp = client.get("/api/v1/schema")
    data = resp.get_json()["data"]
    assert "input_cards" in data and "output_cards" in data


def test_a2a_without_auth_is_401(client) -> None:
    resp = client.post("/a2a", json={"jsonrpc": "2.0", "method": "tasks/send", "params": {}, "id": 1})
    assert resp.status_code == 401


def test_a2a_with_token(client, token) -> None:
    payload = {
        "jsonrpc": "2.0",
        "method": "tasks/send",
        "params": {
            "task": {
                "messages": [
                    {"role": "user", "parts": [{"type": "text", "content": "hello"}]}
                ]
            }
        },
        "id": 1,
    }
    resp = client.post(
        "/a2a",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["result"]["task"]["status"] == "completed"


def test_a2a_with_api_key(client) -> None:
    payload = {
        "jsonrpc": "2.0",
        "method": "tasks/get",
        "params": {"task_id": "task-123"},
        "id": 2,
    }
    resp = client.post(
        "/a2a",
        json=payload,
        headers={"X-API-Key": "dev-api-key"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)


def test_list_agents_requires_auth(client) -> None:
    resp = client.get("/api/v1/agents")
    assert resp.status_code == 401


def test_list_agents_with_token(client, token) -> None:
    resp = client.get("/api/v1/agents", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) > 0


def test_issue_token(client) -> None:
    resp = client.post("/api/v1/security/token", json={"identity": "alice", "scopes": ["a2a:read"]})
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "token" in data
    assert data["identity"] == "alice"
