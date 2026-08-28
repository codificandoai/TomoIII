"""Tests del protocolo Gossip."""
from __future__ import annotations

from config import GossipConfig
from gossip import GossipProtocol


def test_create_fragment_adds_to_kb() -> None:
    gp = GossipProtocol("a", ["b", "c"])
    frag = gp.create_fragment("weather", {"temp": 25}, confidence=0.9)
    assert "weather" in gp.knowledge_base
    assert gp.knowledge_base["weather"].confidence == 0.9


def test_create_fragment_queues_outbox() -> None:
    gp = GossipProtocol("a", ["b", "c"])
    gp.create_fragment("topic1", {"data": 1})
    outbox = gp.flush_outbox()
    assert len(outbox) == 2  # one per neighbor
    targets = {dest for dest, _ in outbox}
    assert targets == {"b", "c"}


def test_receive_accepts_new_fragment() -> None:
    gp = GossipProtocol("b", ["a", "c"], config=GossipConfig(max_hops=3, decay_factor=0.9))
    sender = GossipProtocol("a", ["b"])
    frag = sender.create_fragment("news", {"event": "rain"}, confidence=1.0)
    accepted = gp.receive(frag)
    assert accepted is True
    assert "news" in gp.knowledge_base


def test_receive_rejects_duplicate() -> None:
    gp = GossipProtocol("b", ["a"])
    sender = GossipProtocol("a", ["b"])
    frag = sender.create_fragment("dup", {"x": 1})
    gp.receive(frag)
    accepted_again = gp.receive(frag)
    assert accepted_again is False


def test_receive_decays_confidence() -> None:
    config = GossipConfig(max_hops=5, decay_factor=0.8)
    gp_a = GossipProtocol("a", ["b"], config=config)
    gp_b = GossipProtocol("b", ["c"], config=config)
    frag = gp_a.create_fragment("decay_test", {"v": 1}, confidence=1.0)
    gp_b.receive(frag)
    outbox = gp_b.flush_outbox()
    # Forwarded fragment should have decayed confidence
    forwarded = [f for _, f in outbox if f.topic == "decay_test"]
    assert len(forwarded) >= 1
    assert forwarded[0].confidence < 1.0


def test_max_hops_stops_propagation() -> None:
    config = GossipConfig(max_hops=1, decay_factor=0.9)
    gp = GossipProtocol("b", ["c"], config=config)
    from models import KnowledgeFragment
    frag = KnowledgeFragment(source_agent="a", topic="t", content={}, confidence=0.9, hop_count=1, max_hops=1, seen_by=["a"])
    accepted = gp.receive(frag)
    assert accepted is False
