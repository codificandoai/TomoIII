"""Tests de integración de la API Flask de UC-296."""
from __future__ import annotations


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["service"] == "uc296-memory-agi"


def test_schema(client):
    resp = client.get("/api/v1/schema")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "input_cards" in data
    assert "output_cards" in data


def test_memory_route_sql(client):
    resp = client.post(
        "/api/v1/memory/route",
        json={"query": "costo de SKU-001", "context": {"entity_type": "products", "entity_id": "SKU-001", "attribute": "cost"}},
    )
    assert resp.status_code == 200
    result = resp.get_json()["data"]
    assert result["intent"] == "FACTUAL_LOOKUP"
    assert result["data"] == {"cost": 100.0}


def test_memory_route_self_model(client):
    resp = client.post(
        "/api/v1/memory/route",
        json={"query": "cuál es mi objetivo actual"},
    )
    assert resp.status_code == 200
    result = resp.get_json()["data"]
    assert result["intent"] == "SELF_MODEL"
    assert "current_goal" in result["data"]


def test_store_and_retrieve_working_memory(client):
    client.post("/api/v1/memory/store_working", json={"content": "margen = 25%", "note_type": "calc"})
    resp = client.post(
        "/api/v1/memory/route",
        json={"query": "acabo de calcular el margen"},
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "margen = 25%" in str(data["data"])


def test_spotlight(client):
    candidates = [
        {"item_id": "hyp_1", "item_type": "hypothesis", "content": {"confidence": 0.95}},
        {"item_id": "hyp_2", "item_type": "hypothesis", "content": {"confidence": 0.3}},
    ]
    resp = client.post(
        "/api/v1/memory/spotlight",
        json={"candidates": candidates, "current_goal": "Maximizar retorno"},
    )
    assert resp.status_code == 200
    selected = resp.get_json()["data"]["selected"]
    assert len(selected) > 0
    assert selected[0]["item_id"] == "hyp_1"


def test_goal_proposal_rejected(client):
    resp = client.post(
        "/api/v1/memory/self_model/goal",
        json={"proposed_goal": "Objetivo prohibido", "reason": "Quiero"},
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["status"] == "rejected"


def test_goal_proposal_approved(client):
    resp = client.post(
        "/api/v1/memory/self_model/goal",
        json={
            "proposed_goal": "Minimizar drawdown",
            "reason": "Tasa de éxito reciente baja del 35% tras 5 episodios.",
            "context": {"metrics": {"success_rate": 0.35}},
            "approved": True,
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["status"] in ("applied", "awaiting_approval")


def test_evaluate(client):
    resp = client.post(
        "/api/v1/memory/evaluate",
        json={"task": "test_task", "success": True, "metrics": {"reward": 0.01}},
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["episode"]["task"] == "test_task"
    assert "reflection" in data


def test_brain_memory_pipeline(client):
    import time
    from market_data import SyntheticMarketDataGenerator
    gen = SyntheticMarketDataGenerator(seed=123)
    ticks = [t.to_dict() for t in gen.generate_ticks("AAPL", n=80, start_price=150.0)]
    resp = client.post(
        "/api/v1/brain/memory_pipeline",
        json={
            "symbols": ["AAPL"],
            "ticks": ticks,
            "portfolio": {"cash": 100000.0, "positions": {}},
            "mode": "paper",
            "approved": False,
            "propose_goal": True,
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "trading_output" in data
    assert "tot_prediction" in data
    assert "spotlight" in data
    assert "reflection" in data
