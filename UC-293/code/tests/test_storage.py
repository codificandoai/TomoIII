"""Tests de persistencia SQLite."""
from __future__ import annotations

import tempfile

from sqlite_store import SQLiteStore


def test_sqlite_save_and_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SQLiteStore(f"{tmpdir}/test.db")
        transition = {
            "transition_id": "t1",
            "prev_state": {"request_id": "r1"},
            "action": {"symbol": "AAPL", "side": "BUY"},
            "next_state": {},
            "reward": 1.0,
            "probability": 0.9,
            "info": {},
            "timestamp": "2026-01-01T00:00:00Z",
        }
        store.save_transition(transition)
        rows = store.get_transitions()
        assert len(rows) == 1
        assert rows[0]["transition_id"] == "t1"
