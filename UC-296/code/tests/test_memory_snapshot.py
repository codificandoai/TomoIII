"""UC-296 — Tests for redacted_snapshot used by UC-324 safe shutdown."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory_router import IntelligentMemoryRouter


def test_redacted_snapshot_no_raw_content():
    router = IntelligentMemoryRouter()
    router.store_working_memory("this is a private secret note")
    snap = router.redacted_snapshot("sd-296-001")
    assert "manifest_hash" in snap
    assert snap.get("raw_data_included") is False
    assert "private secret note" not in str(snap)
    assert isinstance(snap.get("notepad_entry_count"), int)
    assert isinstance(snap.get("vector_entry_count"), int)
