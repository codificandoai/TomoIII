"""Tests del MultiLayerMemorySystem para UC-277."""
from memory_system import MultiLayerMemorySystem
from models import MemoryImportance, MemoryType


def _system():
    return MultiLayerMemorySystem("test_agent", db_path=":memory:")


def test_store_interaction():
    ms = _system()
    ep_id = ms.store_interaction("User asked about BTC price", tags=["btc"])
    assert ep_id is not None
    assert len(ms.episodic.episodes) == 1


def test_store_interaction_updates_working():
    ms = _system()
    ms.store_interaction("Test interaction", episode_type="trade")
    assert ms.working.get("last_trade") == "Test interaction"
    assert ms.working.get("last_interaction") == "Test interaction"


def test_store_critical_extracts_facts():
    ms = _system()
    ms.store_interaction(
        "Bitcoin reached all-time high",
        importance=MemoryImportance.CRITICAL,
        extract_facts=True,
    )
    # Should have extracted to semantic
    assert len(ms.semantic.nodes) >= 1


def test_store_low_importance_no_extract():
    ms = _system()
    ms.store_interaction("Trivial note", importance=MemoryImportance.LOW)
    assert len(ms.semantic.nodes) == 0


def test_recall_episodic():
    ms = _system()
    ms.store_interaction("Machine learning models are powerful")
    ms.store_interaction("Cooking pasta is easy")
    result = ms.recall("machine learning", layers=[MemoryType.EPISODIC])
    assert "episodic" in result
    assert len(result["episodic"]) >= 1


def test_recall_semantic():
    ms = _system()
    ms.semantic.add_fact("test_agent", "Bitcoin is a cryptocurrency")
    result = ms.recall("crypto", layers=[MemoryType.SEMANTIC])
    assert "semantic" in result


def test_recall_multi_layer():
    ms = _system()
    ms.store_interaction("BTC event", importance=MemoryImportance.CRITICAL)
    result = ms.recall("BTC")
    assert "episodic" in result
    assert "semantic" in result


def test_consolidate():
    ms = _system()
    ms.store_interaction("Important fact 1", importance=MemoryImportance.HIGH)
    ms.store_interaction("Trivial note", importance=MemoryImportance.LOW)
    ms.store_interaction("Critical fact 2", importance=MemoryImportance.CRITICAL)
    result = ms.consolidate()
    assert result["episodes_processed"] == 3
    assert result["consolidated_to_semantic"] >= 2


def test_new_session():
    ms = _system()
    ms.working.put("data", "value")
    old = ms.working.session_id
    new = ms.new_session()
    assert new != old
    assert len(ms.working.items) == 0


def test_get_system_stats():
    ms = _system()
    ms.store_interaction("Ep1")
    ms.semantic.add_fact("test_agent", "Fact1")
    stats = ms.get_system_stats()
    assert stats["agent_id"] == "test_agent"
    assert "episodic" in stats
    assert "semantic" in stats
    assert "procedural" in stats
    assert "goals" in stats


def test_multi_session_recall():
    ms = _system()
    session_1 = ms.working.session_id
    ms.store_interaction("Session 1 event")
    ms.new_session()
    ms.store_interaction("Session 2 event")
    # Can recall from session 1
    eps = ms.episodic.recall_by_session(session_1)
    assert len(eps) == 1
    assert eps[0].summary == "Session 1 event"
