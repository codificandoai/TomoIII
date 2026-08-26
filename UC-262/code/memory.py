"""Memoria a largo plazo del usuario para UC-262."""
from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, Optional

from models import UserProfile


class LongTermMemory:
    """Almacena perfiles de usuario, reglas aprendidas y políticas exitosas.

    Si ``path`` se configura, persiste perfiles en disco como JSONL.
    De lo contrario opera en memoria.
    """

    _lock = threading.Lock()

    def __init__(self, path: Optional[str] = None) -> None:
        self._path = path or ""
        self._memory: Dict[str, Dict[str, Any]] = {}
        if self._path and os.path.exists(self._path):
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    user_id = data.get("user_id")
                    if user_id:
                        self._memory[user_id] = data
        except (json.JSONDecodeError, OSError):
            self._memory = {}

    def _persist(self) -> None:
        if not self._path:
            return
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                for profile in self._memory.values():
                    f.write(json.dumps(profile, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def get_profile(self, user_id: str) -> UserProfile:
        with self._lock:
            data = self._memory.get(user_id)
            if data:
                return UserProfile.from_dict(data)
            return UserProfile(user_id=user_id)

    def save_profile(self, profile: UserProfile) -> None:
        from models import now_iso

        with self._lock:
            profile.updated_at = now_iso()
            self._memory[profile.user_id] = profile.to_dict()
            self._persist()

    def reset(self) -> None:
        with self._lock:
            self._memory.clear()
