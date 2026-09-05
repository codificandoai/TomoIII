"""Tests de integración para UC-317 — API REST Flask."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_317 import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"


def test_schema(client):
    resp = client.get("/api/v1/schema")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "input_cards" in data
    assert "output_cards" in data
    assert "POST /api/v1/kernel/sessions" in data["input_cards"]


def test_list_models(client):
    resp = client.get("/api/v1/kernel/models")
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(m["name"] == "mock" for m in data["models"])


def test_list_tools(client):
    resp = client.get("/api/v1/kernel/tools")
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(t["name"] == "calculator" for t in data["tools"])


def test_list_roles(client):
    resp = client.get("/api/v1/kernel/roles")
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(r["name"] == "admin" for r in data["roles"])


def test_create_session_and_chat(client):
    # Crear sesión
    resp = client.post("/api/v1/kernel/sessions", json={"name": "api-test", "roles": ["user"], "model": "mock"})
    assert resp.status_code == 200
    data = resp.get_json()
    agent_id = data["agent_id"]
    assert agent_id

    # Chat
    resp2 = client.post("/api/v1/kernel/chat", json={"agent_id": agent_id, "message": "hello"})
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    assert data2["response"]
    assert data2["agent_id"] == agent_id


def test_chat_missing_fields(client):
    resp = client.post("/api/v1/kernel/chat", json={"agent_id": "x"})
    assert resp.status_code == 400


def test_chat_unknown_agent(client):
    resp = client.post("/api/v1/kernel/chat", json={"agent_id": "unknown", "message": "hi"})
    assert resp.status_code == 404


def test_syscall_llm(client):
    # Crear sesión primero
    resp = client.post("/api/v1/kernel/sessions", json={"name": "syscall-test", "roles": ["user"]})
    agent_id = resp.get_json()["agent_id"]

    resp2 = client.post("/api/v1/kernel/syscall", json={
        "agent_id": agent_id,
        "syscall_type": "llm",
        "operation": "llm.generate",
        "payload": {"messages": [{"role": "user", "content": "hello"}]},
    })
    assert resp2.status_code == 200
    data = resp2.get_json()
    assert data["success"]


def test_syscall_invalid_type(client):
    resp = client.post("/api/v1/kernel/syscall", json={
        "agent_id": "x",
        "syscall_type": "invalid",
        "operation": "x",
        "payload": {},
    })
    assert resp.status_code == 400


def test_schedule(client):
    resp = client.post("/api/v1/kernel/schedule", json={"agent_id": "a1", "goal": "test goal"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["task_id"]
    assert data["status"] == "pending"


def test_tools_call(client):
    resp = client.post("/api/v1/kernel/tools/call", json={"name": "calculator", "args": {"expression": "3+3"}})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"]
    assert data["result"] == 6


def test_storage_save_load(client):
    resp = client.post("/api/v1/kernel/storage", json={"key": "api_test", "data": {"v": 123}})
    assert resp.status_code == 200
    assert resp.get_json()["saved"] == "api_test"

    resp2 = client.get("/api/v1/kernel/storage/api_test")
    assert resp2.status_code == 200
    assert resp2.get_json()["data"]["v"] == 123


def test_storage_not_found(client):
    resp = client.get("/api/v1/kernel/storage/nonexistent_key_xyz")
    assert resp.status_code == 404


def test_scheduler_status(client):
    resp = client.get("/api/v1/kernel/scheduler/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "completed" in data
    assert "max_concurrent" in data
