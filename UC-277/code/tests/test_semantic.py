"""Tests del SemanticMemory para UC-277."""
from embeddings import SimpleEmbeddingModel
from semantic_memory import SemanticMemory


def _mem():
    model = SimpleEmbeddingModel(dim=64)
    return SemanticMemory(model, similarity_threshold=0.85)


def test_add_fact():
    mem = _mem()
    node_id = mem.add_fact("agent1", "Bitcoin is a cryptocurrency")
    assert node_id in mem.nodes
    assert mem.nodes[node_id].content == "Bitcoin is a cryptocurrency"


def test_add_fact_deduplication():
    mem = _mem()
    id1 = mem.add_fact("agent1", "Bitcoin is a cryptocurrency")
    id2 = mem.add_fact("agent1", "Bitcoin is a cryptocurrency")  # same text
    assert id1 == id2
    assert mem.nodes[id1].confidence > 0.8  # strengthened


def test_add_preference_positive():
    mem = _mem()
    node_id = mem.add_preference("agent1", "likes morning meetings", 0.8)
    assert mem.nodes[node_id].node_type == "preference_positive"


def test_add_preference_negative():
    mem = _mem()
    node_id = mem.add_preference("agent1", "dislikes spam emails", -0.7)
    assert mem.nodes[node_id].node_type == "preference_negative"


def test_add_relation():
    mem = _mem()
    id1 = mem.add_fact("agent1", "Machine learning")
    id2 = mem.add_fact("agent1", "Deep learning neural networks")
    mem.add_relation(id1, id2, "contains")
    assert len(mem.edges) == 1
    assert mem.edges[0].relation == "contains"


def test_add_relation_reinforcement():
    mem = _mem()
    id1 = mem.add_fact("agent1", "A concept")
    id2 = mem.add_fact("agent1", "Another different concept")
    mem.add_relation(id1, id2, "related_to", strength=0.5)
    mem.add_relation(id1, id2, "related_to", strength=0.5)
    # Should reinforce, not duplicate
    assert len(mem.edges) == 1
    assert mem.edges[0].strength > 0.5


def test_query():
    mem = _mem()
    mem.add_fact("agent1", "Bitcoin is decentralized digital currency")
    mem.add_fact("agent1", "Python is a programming language")
    results = mem.query("agent1", "cryptocurrency Bitcoin", top_k=2)
    assert len(results) >= 1
    # At least one result should contain Bitcoin
    contents = [r["content"] for r in results]
    assert any("Bitcoin" in c for c in contents)


def test_get_preferences():
    mem = _mem()
    mem.add_preference("agent1", "likes conservative trades", 0.9)
    mem.add_preference("agent1", "dislikes high leverage", -0.8)
    prefs = mem.get_preferences("agent1")
    assert len(prefs["positive"]) == 1
    assert len(prefs["negative"]) == 1


def test_get_stats():
    mem = _mem()
    mem.add_fact("agent1", "Fact one")
    mem.add_fact("agent1", "Fact two about something else")
    stats = mem.get_stats("agent1")
    assert stats["total_nodes"] == 2


def test_isolation_between_agents():
    mem = _mem()
    mem.add_fact("agent1", "Agent 1 fact")
    mem.add_fact("agent2", "Agent 2 fact")
    results = mem.query("agent1", "fact", top_k=5)
    assert all(r["node_id"].startswith("agent1") for r in results)
