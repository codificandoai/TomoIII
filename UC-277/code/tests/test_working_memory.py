"""Tests del WorkingMemory para UC-277."""
from working_memory import WorkingMemory


def test_put_and_get():
    wm = WorkingMemory(capacity=5)
    wm.put("key1", "value1")
    assert wm.get("key1") == "value1"


def test_get_missing_key():
    wm = WorkingMemory(capacity=5)
    assert wm.get("nonexistent") is None


def test_capacity_eviction():
    wm = WorkingMemory(capacity=3)
    wm.put("a", "1", priority=0.1)
    wm.put("b", "2", priority=0.5)
    wm.put("c", "3", priority=0.9)
    # Should evict lowest priority when adding 4th
    wm.put("d", "4", priority=0.8)
    assert len(wm.items) == 3
    # "a" had lowest priority, should be evicted
    assert wm.get("a") is None


def test_update_existing():
    wm = WorkingMemory(capacity=5)
    wm.put("key", "v1")
    wm.put("key", "v2")
    assert wm.get("key") == "v2"
    assert wm.items["key"].access_count >= 1


def test_get_context_snapshot():
    wm = WorkingMemory(capacity=5)
    wm.put("name", "Alice")
    wm.put("task", "analysis")
    snap = wm.get_context_snapshot()
    assert snap["item_count"] == 2
    assert snap["items"]["name"] == "Alice"
    assert "session_id" in snap


def test_clear():
    wm = WorkingMemory(capacity=5)
    wm.put("a", "1")
    wm.put("b", "2")
    wm.clear()
    assert len(wm.items) == 0


def test_remove():
    wm = WorkingMemory(capacity=5)
    wm.put("a", "1")
    assert wm.remove("a") is True
    assert wm.get("a") is None
    assert wm.remove("nonexistent") is False


def test_new_session():
    wm = WorkingMemory(capacity=5)
    wm.put("data", "value")
    old_session = wm.session_id
    new_session = wm.new_session()
    assert new_session != old_session
    assert len(wm.items) == 0
