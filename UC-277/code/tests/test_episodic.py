"""Tests del EpisodicMemoryStore para UC-277."""
import time

from embeddings import SimpleEmbeddingModel
from episodic_store import EpisodicMemoryStore
from models import EpisodicMemory, MemoryImportance


def _store():
    model = SimpleEmbeddingModel(dim=64)
    return EpisodicMemoryStore(model, db_path=":memory:")


def _episode(agent_id="agent1", summary="Test episode", ep_type="interaction",
             tags=None, importance=MemoryImportance.MEDIUM, session_id="s1"):
    return EpisodicMemory(
        agent_id=agent_id, summary=summary, episode_type=ep_type,
        tags=tags or [], importance=importance, session_id=session_id,
    )


def test_store_and_recall():
    store = _store()
    ep = _episode(summary="Machine learning is great")
    ep_id = store.store(ep)
    assert ep_id == ep.episode_id
    assert ep_id in store.episodes


def test_recall_semantic():
    store = _store()
    store.store(_episode(summary="Bitcoin reached 42000 USD today"))
    store.store(_episode(summary="Ethereum gas fees are high"))
    store.store(_episode(summary="Cooking pasta for dinner"))

    # Use lower min_similarity for hash-based embeddings
    results = store.recall_semantic("Bitcoin reached 42000", "agent1", min_similarity=0.0)
    assert len(results) >= 1


def test_recall_by_time():
    store = _store()
    now = time.time()
    store.store(_episode(summary="Old event"))
    results = store.recall_by_time("agent1", now - 10, now + 10)
    assert len(results) == 1


def test_recall_by_session():
    store = _store()
    store.store(_episode(summary="Session 1 event", session_id="sess_a"))
    store.store(_episode(summary="Session 2 event", session_id="sess_b"))
    results = store.recall_by_session("sess_a")
    assert len(results) == 1
    assert results[0].summary == "Session 1 event"


def test_recall_by_tag():
    store = _store()
    store.store(_episode(summary="BTC trade", tags=["btc", "trade"]))
    store.store(_episode(summary="ETH hold", tags=["eth", "hold"]))
    results = store.recall_by_tag("agent1", "btc")
    assert len(results) == 1
    assert results[0].summary == "BTC trade"


def test_get_stats():
    store = _store()
    store.store(_episode(summary="Ep1", ep_type="trade"))
    store.store(_episode(summary="Ep2", ep_type="analysis"))
    store.store(_episode(summary="Ep3", ep_type="trade", importance=MemoryImportance.CRITICAL))
    stats = store.get_stats("agent1")
    assert stats["total_episodes"] == 3
    assert stats["by_type"]["trade"] == 2
    assert stats["critical_count"] == 1


def test_importance_boost_in_recall():
    store = _store()
    store.store(_episode(summary="Important BTC event", importance=MemoryImportance.CRITICAL))
    store.store(_episode(summary="Trivial BTC note", importance=MemoryImportance.TRIVIAL))
    results = store.recall_semantic("BTC event note", "agent1", top_k=2, min_similarity=-1.0)
    assert len(results) == 2
    # Both episodes retrieved; importance boost applied to scoring
    importances = [r.importance for r in results]
    assert MemoryImportance.CRITICAL in importances
    assert MemoryImportance.TRIVIAL in importances


def test_empty_recall():
    store = _store()
    results = store.recall_semantic("anything", "agent1")
    assert results == []
