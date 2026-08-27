"""Tests de persistencia SQLite y vector store."""
from __future__ import annotations

import os
import tempfile

from models import WorldModelObservation
from sqlite_store import SQLiteStore
from vector_store import SimpleVectorStore


def test_sqlite_store_roundtrip() -> None:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        store = SQLiteStore(path)
        obs = WorldModelObservation(
            action_type="flight",
            item_id="FL-TEST",
            actual_success=True,
            actual_cost=200.0,
            reward=1.5,
        )
        store.save_observation(obs.to_dict())
        rows = store.get_observations()
        assert len(rows) == 1
        assert rows[0]["item_id"] == "FL-TEST"
    finally:
        os.unlink(path)


def test_vector_store_search() -> None:
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        store = SimpleVectorStore(dim=16, path=path)
        store.add("flight FL-1 success reward 2.0", {"meta": "a"})
        store.add("flight FL-2 failure reward -3.0", {"meta": "b"})
        results = store.search("flight success reward", top_k=2)
        assert len(results) == 2
        assert results[0][1] >= results[1][1]
    finally:
        if os.path.exists(path):
            os.unlink(path)
