"""UC-317 — Storage Manager: persistencia simple de knowledge/state."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class StorageManager:
    """Persistencia en disco (fallback local)."""

    def __init__(self, base_dir: Optional[str] = None) -> None:
        self.base_dir = base_dir or os.path.join(os.path.dirname(__file__), "uc317_storage")
        os.makedirs(self.base_dir, exist_ok=True)

    def _path(self, key: str) -> str:
        return os.path.join(self.base_dir, f"{key}.json")

    def save(self, key: str, data: Any) -> None:
        with open(self._path(key), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, key: str) -> Optional[Any]:
        path = self._path(key)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def delete(self, key: str) -> bool:
        path = self._path(key)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def list_keys(self) -> List[str]:
        return [f[:-5] for f in os.listdir(self.base_dir) if f.endswith(".json")]
