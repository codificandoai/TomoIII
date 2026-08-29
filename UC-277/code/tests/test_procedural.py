"""Tests del ProceduralMemory para UC-277."""
from embeddings import SimpleEmbeddingModel
from procedural_memory import ProceduralMemory


def _mem():
    model = SimpleEmbeddingModel(dim=64)
    return ProceduralMemory(model)


def test_learn_skill():
    mem = _mem()
    skill_id = mem.learn_skill(
        "agent1", "Technical Analysis", "Identify support and resistance",
        "trading", {"timeframe": "4h"}
    )
    assert skill_id in mem.skills
    assert mem.skills[skill_id].name == "Technical Analysis"
    assert mem.skills[skill_id].success_count == 1


def test_learn_skill_initial_failure():
    mem = _mem()
    skill_id = mem.learn_skill(
        "agent1", "Risky Strategy", "High leverage trades",
        "trading", {}, initial_success=False
    )
    assert mem.skills[skill_id].failure_count == 1
    assert mem.skills[skill_id].success_count == 0


def test_update_outcome_success():
    mem = _mem()
    skill_id = mem.learn_skill("agent1", "Skill", "desc", "cat", {})
    mem.update_outcome(skill_id, True, 0.9)
    assert mem.skills[skill_id].success_count == 2


def test_update_outcome_failure():
    mem = _mem()
    skill_id = mem.learn_skill("agent1", "Skill", "desc", "cat", {})
    mem.update_outcome(skill_id, False, 0.3)
    assert mem.skills[skill_id].failure_count == 1


def test_update_outcome_ema():
    mem = _mem()
    skill_id = mem.learn_skill("agent1", "Skill", "desc", "cat", {})
    mem.update_outcome(skill_id, True, 0.9)
    # EMA: 0.3 * 0.9 + 0.7 * 0.5 = 0.62
    assert abs(mem.skills[skill_id].avg_outcome_score - 0.62) < 0.01


def test_refine_skill():
    mem = _mem()
    skill_id = mem.learn_skill("agent1", "Skill", "desc", "cat", {"a": 1})
    mem.refine_skill(skill_id, {"a": 2, "b": 3})
    assert mem.skills[skill_id].parameters == {"a": 2, "b": 3}
    assert mem.skills[skill_id].version == 2


def test_retrieve_best():
    mem = _mem()
    mem.learn_skill("agent1", "BTC Analysis", "Analyze Bitcoin price", "trading", {})
    mem.learn_skill("agent1", "Cooking", "Make pasta", "food", {})
    results = mem.retrieve_best("agent1", "Bitcoin price analysis")
    assert len(results) >= 1
    # Both skills should be returned (hash-based similarity is approximate)
    names = [s.name for s in results]
    assert "BTC Analysis" in names


def test_retrieve_best_by_category():
    mem = _mem()
    mem.learn_skill("agent1", "Trade BTC", "desc", "trading", {})
    mem.learn_skill("agent1", "Cook Pasta", "desc", "food", {})
    results = mem.retrieve_best("agent1", "anything", category="food")
    assert all(s.category == "food" for s in results)


def test_mastery_levels():
    mem = _mem()
    skill_id = mem.learn_skill("agent1", "Skill", "desc", "cat", {})
    assert mem.skills[skill_id].mastery_level == "novice"


def test_success_rate():
    mem = _mem()
    skill_id = mem.learn_skill("agent1", "Skill", "desc", "cat", {})
    for _ in range(4):
        mem.update_outcome(skill_id, True, 0.8)
    mem.update_outcome(skill_id, False, 0.3)
    # 5 success, 1 failure = 5/6 ≈ 0.833
    assert mem.skills[skill_id].success_rate > 0.8


def test_get_stats():
    mem = _mem()
    mem.learn_skill("agent1", "S1", "d1", "cat", {})
    mem.learn_skill("agent1", "S2", "d2", "cat", {})
    stats = mem.get_stats("agent1")
    assert stats["total_skills"] == 2


def test_get_stats_empty():
    mem = _mem()
    stats = mem.get_stats("agent1")
    assert stats["total_skills"] == 0
