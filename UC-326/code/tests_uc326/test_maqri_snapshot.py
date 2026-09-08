"""UC-326 — Tests for MAQRI redacted_snapshot used by UC-324 safe shutdown."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from maqri_engine import MaqriEngine


def test_maqri_redacted_snapshot_no_raw_content():
    engine = MaqriEngine()
    # Add some search history without triggering external network
    engine._history.append(None)  # type: ignore
    snap = engine.redacted_snapshot("sd-326-001")
    assert "manifest_hash" in snap
    assert snap.get("raw_data_included") is False
    # ensure no raw memory contents; key raw_data_included is intentional metadata
    assert "private" not in str(snap).lower()
    assert isinstance(snap.get("episodic_entry_count"), int)
    assert isinstance(snap.get("search_history_count"), int)
