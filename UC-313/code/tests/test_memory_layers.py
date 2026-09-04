"""Tests unitarios de las capas de memoria AGI de UC-296."""
from __future__ import annotations

import pytest

from attention_spotlight import AttentionSpotlight
from continuous_self_eval import ContinuousSelfEvaluator
from memory_config import (
    MemoryConfig,
    SelfModelConfig,
    ShortTermMemoryConfig,
    StructuredMemoryConfig,
    VectorMemoryConfig,
)
from memory_router import IntelligentMemoryRouter
from memory_types import MemoryIntent, SpotlightItem
from metacognitive_goals import GoalManager
from self_model_store import SelfModelStore
from short_term_memory import ShortTermNotepad
from structured_memory import StructuredMemory


def test_notepad_fifo_capacity():
    pad = ShortTermNotepad(ShortTermMemoryConfig(max_notes=3))
    pad.store("a")
    pad.store("b")
    pad.store("c")
    pad.store("d")
    notes = pad.retrieve_latest(n=10)
    assert len(notes) == 3
    assert notes[0].content == "b"


def test_structured_memory_crud(tmp_path):
    cfg = StructuredMemoryConfig(sqlite_path=str(tmp_path / "test.db"))
    mem = StructuredMemory(cfg)
    mem.store("products", "SKU-001", "cost", 123.0)
    assert mem.query("products", "SKU-001", "cost") == 123.0


def test_memory_router_classifies_intents():
    router = IntelligentMemoryRouter()
    assert router.classify_intent("costo de SKU-001") == MemoryIntent.FACTUAL_LOOKUP
    assert router.classify_intent("acabo de calcular el margen") == MemoryIntent.WORKING_STATE
    assert router.classify_intent("cuál es mi objetivo") == MemoryIntent.SELF_MODEL
    assert router.classify_intent("qué pasó en la guerra de precios") == MemoryIntent.SEMANTIC_RECALL


def test_memory_router_retrieves_fact(tmp_path):
    cfg = MemoryConfig(structured=StructuredMemoryConfig(sqlite_path=str(tmp_path / "router.db")))
    router = IntelligentMemoryRouter(cfg)
    result = router.retrieve(
        "costo de SKU-001",
        context={"entity_type": "products", "entity_id": "SKU-001", "attribute": "cost"},
    )
    assert result.intent == MemoryIntent.FACTUAL_LOOKUP
    assert result.data == {"cost": 100.0}


def test_self_model_store_defaults_and_update(tmp_path):
    cfg = SelfModelConfig(
        persistence_path=str(tmp_path / "self.json"),
        sqlite_path=str(tmp_path / "self.db"),
    )
    store = SelfModelStore(cfg)
    model = store.load()
    assert model["current_goal"] == "Maximizar retorno ajustado por riesgo"
    store.update_competence("tick_prediction", 0.9)
    model = store.load()
    assert model["competence_profile"]["tick_prediction"] == pytest.approx(0.78, abs=1e-2)


def test_self_model_performance_history(tmp_path):
    cfg = SelfModelConfig(sqlite_path=str(tmp_path / "perf.db"))
    store = SelfModelStore(cfg)
    store.record_performance("test", True, {"reward": 0.01}, {"symbol": "AAPL"})
    store.record_performance("test", False, {"reward": -0.02}, {"symbol": "TSLA"})
    summary = store.get_summary()
    assert summary["performance_attempts"] >= 2


def test_attention_spotlight_selects_best():
    spotlight = AttentionSpotlight()
    candidates = [
        SpotlightItem("low_conf", "hypothesis", {"confidence": 0.2}),
        SpotlightItem("high_conf", "hypothesis", {"confidence": 0.95}),
        SpotlightItem("tot", "tot_prediction", {"confidence": 0.85}),
    ]
    selected = spotlight.select(candidates, current_goal="Maximizar retorno ajustado por riesgo")
    assert len(selected) <= spotlight.config.max_items_in_workspace
    assert selected[0].item_id == "high_conf"


def test_goal_manager_rejects_unsafe_goal():
    gm = GoalManager()
    result = gm.apply_goal_change(
        current_goal="Maximizar retorno ajustado por riesgo",
        proposed_goal="Objetivo no permitido",
        reason="Quiero",
        context={},
        approved=True,
    )
    assert result["status"] == "rejected"


def test_goal_manager_applies_allowed_goal():
    gm = GoalManager()
    result = gm.apply_goal_change(
        current_goal="Maximizar retorno ajustado por riesgo",
        proposed_goal="Minimizar drawdown",
        reason="La tasa de éxito cayó al 35% tras 5 episodios con drawdown.",
        context={"metrics": {"success_rate": 0.35}, "events": ["drawdown"]},
        approved=True,
    )
    assert result["status"] == "applied"


def test_continuous_self_eval_reflection(tmp_path):
    cfg = SelfModelConfig(sqlite_path=str(tmp_path / "eval.db"))
    store = SelfModelStore(cfg)
    evaluator = ContinuousSelfEvaluator(store)
    for i in range(5):
        evaluator.evaluate_execution(
            task=f"task_{i}",
            success=i % 2 == 0,
            metrics={"reward": 0.01 if i % 2 == 0 else -0.02},
            context={"symbol": "AAPL"},
        )
    reflection = evaluator.reflect(limit=5)
    assert "success_rate" in reflection
    assert reflection["sample_size"] == 5


def test_vector_memory_search():
    from long_term_memory import LongTermMemory
    mem = LongTermMemory(VectorMemoryConfig(vector_store_path=""))
    mem.add("Guerra de precios con TechCorp")
    results = mem.search("guerra de precios")
    assert len(results) > 0
