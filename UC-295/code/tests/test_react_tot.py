"""Tests unitarios e integración para el cerebro ReAct Híbrido + ToT (UC-295)."""
from __future__ import annotations

import json
import uuid

import pytest

from market_data import SyntheticMarketDataGenerator
from models import MarketTick
from perception import MarketPerceptionPipeline
from react_tot import (
    PredictorResult,
    PredictorStatus,
    ReActReasonactToTBrain,
    ThoughtNode,
    TickPredictionEnvironment,
    ToTNodeState,
)


@pytest.fixture
def ticks():
    gen = SyntheticMarketDataGenerator(seed=123)
    return gen.generate_ticks("AAPL", n=80, start_price=150.0)


@pytest.fixture
def environment():
    return TickPredictionEnvironment(failure_sources=[], latency_ms=0.0)


@pytest.fixture
def brain(environment):
    return ReActReasonactToTBrain(
        environment,
        confidence_threshold=0.5,
        max_depth=2,
    )


# ---------------------------------------------------------------------------
# Unitarios
# ---------------------------------------------------------------------------
def test_environment_query_success(environment, ticks):
    ctx = _build_ctx("AAPL", ticks)
    environment.begin(ctx)
    result = environment.query("world_model", ctx)
    assert result.status == PredictorStatus.SUCCESS
    assert result.predicted_ask > result.predicted_bid > 0.0
    assert result.confidence >= 0.5


def test_environment_simulated_failure(environment, ticks):
    env = TickPredictionEnvironment(failure_sources=["technical"], latency_ms=0.0)
    ctx = _build_ctx("AAPL", ticks)
    env.begin(ctx)
    result = env.query("technical", ctx)
    assert result.status == PredictorStatus.TIMEOUT
    assert result.error is not None


def test_brain_predict_returns_consensus(brain, ticks):
    result = brain.predict(
        symbol="AAPL",
        ticks=ticks,
        predictors=["world_model", "technical", "microstructure"],
    )
    assert result["status"] == "ok"
    final = result["final_prediction"]
    assert final["predicted_ask"] > final["predicted_bid"] > 0.0
    assert final["spread"] >= 0.0
    assert result["tree_summary"]["success_leaves"] >= 1


def test_brain_backtracks_on_failure(ticks):
    env = TickPredictionEnvironment(
        failure_sources=["technical"],
        latency_ms=0.0,
    )
    brain = ReActReasonactToTBrain(env, confidence_threshold=0.5, max_depth=2)
    result = brain.predict(
        symbol="AAPL",
        ticks=ticks,
        predictors=["world_model", "technical", "microstructure"],
    )
    assert result["status"] == "ok"
    assert result["tree_summary"]["success_leaves"] >= 1
    # La rama técnica fue podada y el árbol debe registrar el retroceso o una hoja
    # adicional generada por el fallback.
    assert result["tree_summary"]["total_nodes"] > 4


def test_brain_prunes_low_confidence(ticks):
    env = TickPredictionEnvironment(failure_sources=[], latency_ms=0.0)
    # Umbral imposible para forzar poda de todas las hojas.
    brain = ReActReasonactToTBrain(env, confidence_threshold=1.5, max_depth=2)
    result = brain.predict(
        symbol="AAPL",
        ticks=ticks,
        predictors=["world_model", "technical"],
    )
    assert result["status"] == "ok"
    assert result["final_prediction"] is None
    assert result["tree_summary"]["success_leaves"] == 0
    assert result["tree_summary"]["pruned_leaves"] >= 1


def test_tree_node_states(environment, ticks):
    brain = ReActReasonactToTBrain(environment, confidence_threshold=0.5, max_depth=2)
    result = brain.predict(
        symbol="AAPL",
        ticks=ticks,
        predictors=["world_model", "technical"],
    )
    tree = result["tree"]
    assert tree["action"] == "ROOT"
    assert len(tree["children"]) == 2
    states = {child["state"] for child in tree["children"]}
    assert ToTNodeState.SUCCESS.value in states or ToTNodeState.PRUNED_FAILED.value in states


# ---------------------------------------------------------------------------
# Integración con la API Flask
# ---------------------------------------------------------------------------
def test_api_tot_predict(client, ticks):
    payload = {
        "symbol": "AAPL",
        "ticks": [t.to_dict() for t in ticks],
        "predictors": ["world_model", "technical", "microstructure"],
        "simulate_failures": ["technical"],
        "max_depth": 2,
    }
    resp = client.post(
        "/api/v1/tot/predict",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert "final_prediction" in data
    assert "tree_summary" in data
    assert "tree" in data
    assert data["tree_summary"]["success_leaves"] >= 1


def test_api_tot_predict_no_ticks(client):
    resp = client.post(
        "/api/v1/tot/predict",
        data=json.dumps({"symbol": "AAPL", "ticks": []}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_api_tot_docs(client):
    resp = client.get("/api/v1/tot/docs")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Input Card View" in html
    assert "Output Card View" in html
    assert "predicted_ask" in html


def test_api_tot_predict_with_news(client, ticks):
    payload = {
        "symbol": "AAPL",
        "ticks": [t.to_dict() for t in ticks],
        "predictors": ["sentiment", "ensemble"],
        "news": [{"text": "AAPL strong earnings beat", "source": "bloomberg"}],
    }
    resp = client.post(
        "/api/v1/tot/predict",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["tree_summary"]["success_leaves"] >= 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_ctx(symbol: str, ticks):
    sorted_ticks = sorted(ticks, key=lambda t: t.timestamp)
    pipeline = MarketPerceptionPipeline()
    snapshots = pipeline.perceive(
        request_id=f"test-{uuid.uuid4().hex[:6]}",
        ticks_by_symbol={symbol: sorted_ticks},
        news=[],
    )
    snapshot = snapshots.get(symbol)
    features = snapshot.features.to_dict() if snapshot else {}
    return {
        "symbol": symbol,
        "ticks": sorted_ticks,
        "last_tick": sorted_ticks[-1],
        "news": [],
        "snapshot": snapshot,
        "features": features,
    }
